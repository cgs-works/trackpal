import type { ReactNode } from "react";

interface SafeMarkdownProps {
  source: string;
}

const ALLOWED_EXTERNAL_HELP_URLS = new Set([
  "https://myaccount.google.com/apppasswords",
  "https://support.google.com/accounts/answer/185833",
]);

function allowedExternalHelpUrl(value: string): string | null {
  return ALLOWED_EXTERNAL_HELP_URLS.has(value) ? value : null;
}

const INLINE_TOKEN_PATTERN = /(\*\*[^*]+\*\*|\[[^\]]+\]\(https:\/\/[^)]+\))/g;

function renderInlineMarkdown(value: string): ReactNode {
  const tokens = value.split(INLINE_TOKEN_PATTERN);
  return tokens.map((token, index) => {
    if (token.startsWith("**") && token.endsWith("**")) {
      return <strong key={`${token}-${index}`}>{token.slice(2, -2)}</strong>;
    }

    const linkMatch = token.match(/^\[([^\]]+)\]\((https:\/\/[^)]+)\)$/);
    if (linkMatch) {
      const [, label, destination] = linkMatch;
      const href = allowedExternalHelpUrl(destination);
      return href ? (
        <a
          key={`${href}-${index}`}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          {label}
        </a>
      ) : (
        label
      );
    }

    return token;
  });
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

        if (lines.length > 0 && lines.every((line) => /^\d+\.\s+/.test(line))) {
          return (
            <ol
              key={`ordered-list-${index}`}
              className="flex max-w-none list-decimal flex-col gap-2 pl-5 text-justify text-muted-foreground"
            >
              {lines.map((line, lineIndex) => (
                <li key={`${line}-${lineIndex}`}>
                  {renderInlineMarkdown(line.replace(/^\d+\.\s+/, ""))}
                </li>
              ))}
            </ol>
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
