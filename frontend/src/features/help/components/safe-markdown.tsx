import type { ReactNode } from "react";

interface SafeMarkdownProps {
  source: string;
}

function renderInlineMarkdown(value: string): ReactNode {
  return value.split(/(\*\*[^*]+\*\*)/g).map((part, index) =>
    part.startsWith("**") && part.endsWith("**") ? (
      <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong>
    ) : (
      part
    ),
  );
}

export function SafeMarkdown({ source }: SafeMarkdownProps) {
  const blocks = source.trim().split(/\n\s*\n/);

  return (
    <div className="flex flex-col gap-5">
      {blocks.map((block, index) => {
        const lines = block.split("\n");
        const heading = lines[0]?.match(/^(#{1,3})\s+(.+)$/);
        if (heading) {
          const Heading = heading[1].length === 1 ? "h1" : heading[1].length === 2 ? "h2" : "h3";
          return (
            <Heading
              key={`${heading[1]}-${index}`}
              className={
                Heading === "h1"
                  ? "font-heading text-3xl font-semibold tracking-tight"
                  : "font-heading text-xl font-semibold tracking-tight"
              }
            >
              {renderInlineMarkdown(heading[2])}
            </Heading>
          );
        }

        if (lines.length > 0 && lines.every((line) => /^-\s+/.test(line))) {
          return (
            <ul
              key={`list-${index}`}
              className="flex max-w-none list-disc flex-col gap-2 pl-5 text-justify text-muted-foreground"
            >
              {lines.map((line, lineIndex) => (
                <li key={`${line}-${lineIndex}`}>
                  {renderInlineMarkdown(line.replace(/^-\s+/, ""))}
                </li>
              ))}
            </ul>
          );
        }

        return (
          <p key={`paragraph-${index}`} className="max-w-none text-justify leading-7 text-muted-foreground">
            {renderInlineMarkdown(lines.join(" "))}
          </p>
        );
      })}
    </div>
  );
}
