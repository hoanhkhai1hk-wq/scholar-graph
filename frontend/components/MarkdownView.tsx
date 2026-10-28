import { Fragment, type ReactNode } from "react";
import sanitizeHtml from "sanitize-html";

/**
 * 极简 Markdown 渲染器（全文翻译的版式视图）。
 *
 * 后端 full.markdown 的特点（backend/README.md 第 283 行）：
 * - 每段前有 `<a id="source_chunk_id"></a>`，段级滚动靠它双向对应；
 * - 表格保留原 HTML/Markdown 行列标记；
 * - 代码块、行内代码、LaTeX 与公式块不送模型，由代码按原位置拼回。
 *
 * 因此这里：锚点必须落成真实 DOM 元素；代码块/行内代码/LaTeX 一律原样渲染，
 * 不做任何翻译或转义破坏。表格（本文件为 HTML 表）按原样嵌入。
 */
const ANCHOR = /^<a id="([^"]+)"><\/a>\s*$/;

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  // 行内代码优先，其中的内容原样显示，不做任何处理
  const pattern = /`([^`]+)`/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let index = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) nodes.push(text.slice(last, match.index));
    nodes.push(<code key={`${keyPrefix}-c${index++}`}>{match[1]}</code>);
    last = match.index + match[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

export default function MarkdownView({ markdown }: { markdown: string }) {
  const lines = markdown.split("\n");
  const blocks: ReactNode[] = [];
  let paragraph: string[] = [];
  let key = 0;

  function flushParagraph() {
    if (paragraph.length === 0) return;
    const text = paragraph.join("\n");
    blocks.push(
      <p className="sg-prose" key={`p${key++}`}>
        {renderInline(text, `p${key}`)}
      </p>,
    );
    paragraph = [];
  }

  let index = 0;
  while (index < lines.length) {
    const line = lines[index];

    // 段锚点：落成真实元素，供滚动定位
    const anchor = ANCHOR.exec(line.trim());
    if (anchor) {
      flushParagraph();
      blocks.push(
        <span
          key={`a${key++}`}
          id={anchor[1]}
          data-chunk-id={anchor[1]}
          className="sg-md-anchor"
        />,
      );
      index += 1;
      continue;
    }

    // 代码块：原样，不翻译
    if (line.trim().startsWith("```")) {
      flushParagraph();
      const body: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        body.push(lines[index]);
        index += 1;
      }
      index += 1;
      blocks.push(
        <pre className="sg-code" key={`code${key++}`}>
          <code>{body.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    // 标题
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      flushParagraph();
      const level = Math.min(heading[1].length, 6);
      const Tag = (`h${level}` as unknown) as "h1";
      blocks.push(
        <Tag className="sg-md-heading" key={`h${key++}`}>
          {renderInline(heading[2], `h${key}`)}
        </Tag>,
      );
      index += 1;
      continue;
    }

    // 原样 HTML 块（表格等）：结构与可见内容都来自后端，不改写
    if (/^\s*<(table|tbody|thead|tr|td|th|div|figure)\b/i.test(line)) {
      flushParagraph();
      const body: string[] = [];
      while (index < lines.length && lines[index].trim() !== "") {
        body.push(lines[index]);
        index += 1;
      }
      blocks.push(
        <div
          className="sg-md-html"
          key={`raw${key++}`}
          dangerouslySetInnerHTML={{ __html: sanitizeHtml(body.join("\n"), {
            allowedTags: ["table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption", "div", "figure", "figcaption", "p", "br", "strong", "em", "sub", "sup", "code", "pre", "ul", "ol", "li"],
            allowedAttributes: { th: ["colspan", "rowspan", "scope"], td: ["colspan", "rowspan"] },
            allowedSchemes: [],
          }) }}
        />,
      );
      continue;
    }

    if (line.trim() === "") {
      flushParagraph();
      index += 1;
      continue;
    }

    paragraph.push(line);
    index += 1;
  }
  flushParagraph();

  return <div className="sg-md">{blocks.map((block) => block)}</div>;
}
