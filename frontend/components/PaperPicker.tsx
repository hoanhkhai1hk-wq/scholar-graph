"use client";

import { useState } from "react";
import type { PaperMeta } from "@/lib/types";

/**
 * 论文选择器。单选或复选，选项来自后端 GET /papers 的真实记录。
 */
export default function PaperPicker({
  papers,
  selected,
  onChange,
  multiple = false,
  label = "选择论文",
  disabled = false,
  maxSelections = 100,
}: {
  papers: PaperMeta[];
  selected: string[];
  onChange: (ids: string[]) => void;
  multiple?: boolean;
  label?: string;
  disabled?: boolean;
  maxSelections?: number;
}) {
  const [keyword, setKeyword] = useState("");

  const visible = papers.filter((paper) => {
    if (!keyword.trim()) return true;
    const needle = keyword.trim().toLowerCase();
    return (
      (paper.title ?? "").toLowerCase().includes(needle) ||
      paper.id.toLowerCase().includes(needle)
    );
  });

  function toggle(id: string) {
    if (!multiple) {
      onChange(selected.includes(id) && selected.length === 1 ? [] : [id]);
      return;
    }
    onChange(
      selected.includes(id)
        ? selected.filter((item) => item !== id)
        : [...selected, id],
    );
  }

  return (
    <div className="sg-picker">
      <div className="sg-picker__head">
        <span className="sg-picker__label">
          {label}
          {multiple ? `（可多选，已选 ${selected.length}）` : ""}
        </span>
        <input
          className="sg-input"
          type="search"
          placeholder="搜索论文标题"
          aria-label={`${label}：搜索论文`}
          value={keyword}
          disabled={disabled}
          onChange={(event) => setKeyword(event.target.value)}
        />
      </div>

      {visible.length === 0 ? (
        <p className="sg-mono">没有匹配的论文。</p>
      ) : (
        <ul className="sg-picker__list">
          {visible.map((paper) => {
            const checked = selected.includes(paper.id);
            return (
              <li key={paper.id}>
                <label className="sg-picker__item">
                  <input
                    type={multiple ? "checkbox" : "radio"}
                    name="paper-picker"
                    value={paper.id}
                    checked={checked}
                    disabled={disabled || multiple && !checked && selected.length >= maxSelections}
                    onChange={() => toggle(paper.id)}
                  />
                  <span className="sg-picker__title">
                    {paper.title ?? "（标题未提取）"}
                  </span>
                  <span className="sg-mono">
                    {paper.year ?? "—"} · {paper.version ?? "—"} ·{" "}
                    {paper.page_count ?? "—"} 页
                  </span>

                </label>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
