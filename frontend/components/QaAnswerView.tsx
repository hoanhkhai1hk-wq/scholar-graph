import type { QAAnswer } from "@/lib/types";
import AnchorTag from "./AnchorTag";

const CHECK_TAG: Record<string, string> = {
  passed: "sg-tag sg-tag--success",
  failed: "sg-tag sg-tag--error",
  unverifiable: "sg-tag sg-tag--warning",
  not_applicable: "sg-tag sg-tag--muted",
};

/**
 * QAAnswer 展示。
 * refused=true 时原样展示拒答原因与原文纠错，不把拒答渲染成答案。
 */
export default function QaAnswerView({
  answer,
  title,
}: {
  answer: QAAnswer;
  title?: string;
}) {
  return (
    <div className="sg-qa">
      {title ? <h3 className="sg-subhead">{title}</h3> : null}

      <div className="sg-qa__status">
        <span
          className={
            answer.refused
              ? "sg-tag sg-tag--warning"
              : "sg-tag sg-tag--info"
          }
        >
          {answer.refused ? "证据不足，未形成答案" : "依据原文回答"}
        </span>
      </div>

      <div className="sg-qa__answer">
        {answer.refused ? (
          <div>
            <p className="sg-qa__refused-label">
              当前材料不足以支持回答，下面说明缺少的证据或原文中的纠正信息：
            </p>
            <p className="sg-prose">{answer.answer}</p>
          </div>
        ) : (
          <p className="sg-prose">{answer.answer}</p>
        )}
      </div>

      <h4 className="sg-qa__sub">证据锚点（{answer.anchors.length}）</h4>
      {answer.anchors.length === 0 ? (
        <p className="sg-mono">无锚点（拒答时允许为空）</p>
      ) : (
        <ul className="sg-anchor-list">
          {answer.anchors.map((anchor, index) => (
            <li key={`${anchor.chunk_id}-${index}`}>
              <AnchorTag anchor={anchor} index={index} />
            </li>
          ))}
        </ul>
      )}

      <details className="sg-diag"><summary>数字与原文核对</summary><h4 className="sg-qa__sub">
        数字事实校验 ·{" "}
        <span className={CHECK_TAG[answer.numeric_fact_check.status] ?? "sg-tag"}>
        {{ passed: "已回溯原文", failed: "核对未通过", unverifiable: "无法核实", not_applicable: "无须核对数字" }[answer.numeric_fact_check.status]}
        </span>
      </h4>
      {answer.numeric_fact_check.checks.length === 0 ? (
        <p className="sg-mono">
          无可校验数字事实（not_applicable 时 checks 必须为空）
        </p>
      ) : (
        <table className="sg-table">
          <thead>
            <tr>
              <th>待核数字陈述</th>
              <th>状态</th>
              <th>证据</th>
              <th>校验理由</th>
            </tr>
          </thead>
          <tbody>
            {answer.numeric_fact_check.checks.map((check, index) => (
              <tr key={index}>
                <td>{check.claim}</td>
                <td>
                  <span className={CHECK_TAG[check.status] ?? "sg-tag"}>
                    {check.status}
                  </span>
                </td>
                <td>
                  {check.evidence.length > 0 ? (
                    check.evidence.map((ev, i) => (
                      <AnchorTag key={i} anchor={ev} />
                    ))
                  ) : (
                    <span className="sg-tag sg-tag--warning">无证据</span>
                  )}
                </td>
                <td>{check.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}</details>
    </div>
  );
}
