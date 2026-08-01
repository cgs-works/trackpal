import { beforeEach, describe, expect, it, vi } from "vitest";
import { createIconifyCatalog } from "../icon-catalog";
import { parseIconReference } from "../icon-reference";

describe("Iconify catalog adapter", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("parses only provider-qualified icon references", () => {
    expect(parseIconReference("simple-icons:netflix")).toEqual({
      prefix: "simple-icons",
      name: "netflix",
    });
    expect(parseIconReference("netflix")).toBeNull();
    expect(parseIconReference("Simple-Icons:netflix")).toBeNull();
  });

  it("normalizes search results and collection licenses", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      icons: ["simple-icons:netflix"],
      total: 1,
      limit: 10,
      start: 0,
      collections: {
        "simple-icons": {
          name: "Simple Icons",
          author: { name: "Simple Icons Collaborators", url: "https://simpleicons.org" },
          license: { title: "CC0 1.0", spdx: "CC0-1.0", url: "https://creativecommons.org/publicdomain/zero/1.0/" },
          palette: true,
        },
      },
    }), { status: 200 }));
    const catalog = createIconifyCatalog(fetcher);

    const result = await catalog.search("netflix");

    expect(result.icons).toEqual(["simple-icons:netflix"]);
    expect(result.hasMore).toBe(false);
    expect(result.collections["simple-icons"].license.spdx).toBe("CC0-1.0");
    const requested = new URL(String(fetcher.mock.calls[0][0]));
    expect(requested.searchParams.get("limit")).toBe("10");
  });

  it("sends non-English search text unchanged", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      icons: [], total: 0, limit: 10, start: 0, collections: {},
    }), { status: 200 }));
    const catalog = createIconifyCatalog(fetcher);

    await catalog.search("música");

    const requested = new URL(String(fetcher.mock.calls[0][0]));
    expect(requested.searchParams.get("query")).toBe("música");
  });

  it("loads collection metadata for a saved icon", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      "simple-icons": {
        name: "Simple Icons",
        author: { name: "Simple Icons Collaborators" },
        license: { title: "CC0 1.0", url: "https://creativecommons.org/publicdomain/zero/1.0/" },
        palette: true,
      },
    }), { status: 200 }));
    const catalog = createIconifyCatalog(fetcher);

    const details = await catalog.describe("simple-icons:netflix");

    expect(details.icon).toBe("simple-icons:netflix");
    expect(details.collection.license.title).toBe("CC0 1.0");
    expect(String(fetcher.mock.calls[0][0])).toContain("/collections?prefix=simple-icons");
  });

  it("reuses session cache for repeated searches", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      icons: [], total: 0, limit: 10, start: 0, collections: {},
    }), { status: 200 }));
    const catalog = createIconifyCatalog(fetcher);

    await catalog.search("cloud");
    await catalog.search("cloud");

    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
