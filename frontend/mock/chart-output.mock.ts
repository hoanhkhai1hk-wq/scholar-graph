/**
 * MOCK DATA — 演示假数据，未接后端。
 * 字段与 contracts/chart-output.v1.1.example.json 一致（原样复制）。
 *
 * image_ref 指向 charts/chart-demo-001.png，该文件不存在；
 * 页面只渲染占位框与文字说明，不贴任何假造的实测图。
 */
export const chartOutputMock = [
  {
    schema_version: "1.1.0",
    chart_id: "chart-demo-001",
    chart_type: "bar",
    series: [
      {
        name: "Synthetic samples",
        values: [12, 18],
      },
    ],
    image_ref: "charts/chart-demo-001.png",
    caption:
      "Synthetic illustration only: the sample values are 12 and 18.",
    numeric_checks: [
      {
        value: 12,
        csv_anchor: {
          csv_ref: "fixtures/synthetic.csv",
          row_number: 2,
          column_name: "samples",
        },
        verified: true,
      },
      {
        value: 18,
        csv_anchor: {
          csv_ref: "fixtures/synthetic.csv",
          row_number: 3,
          column_name: "samples",
        },
        verified: true,
      },
    ],
  },
] as const;

export default chartOutputMock;
