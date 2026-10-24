import { unlandedByArea, type EndpointArea } from "@/lib/endpoints";

/**
 * 未落地接口的占位区。
 * 明标「后端接口未落地，暂不可用」，不显示任何伪造数据。
 */
export default function UnavailablePanel({ area }: { area: EndpointArea }) {
  const items = unlandedByArea(area);

  return (
    <section className="sg-section">
      <div className="sg-section__head">
        <h2 className="sg-section__title">未落地能力</h2>
        <span className="sg-section__hint">共 {items.length} 条端点</span>
      </div>

      <div className="sg-note">
        <span className="sg-tag sg-tag--warning">后端接口未落地，暂不可用</span>
        <p className="sg-note__text">
          以下端点在后端实施清单中标注为未落地。页面只保留占位，
          不构造任何数据，也不声称已接通。
        </p>
      </div>

      <table className="sg-table">
        <thead>
          <tr>
            <th>方法</th>
            <th>端点</th>
            <th>能力</th>
            <th>未落地原因与归属</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={`${item.method} ${item.path}`}>
              <td>
                <span className="sg-tag sg-tag--muted">{item.method}</span>
              </td>
              <td className="sg-mono">{item.path}</td>
              <td>{item.label}</td>
              <td>{item.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
