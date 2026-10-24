/**
 * 「演示假数据，未接后端」横幅。
 * 所有页面共用的全局提示，位于页面最顶部。
 */
export default function DemoBanner() {
  return (
    <div className="sg-banner" role="note" aria-label="演示数据提示">
      <span className="sg-banner__label">演示假数据，未接后端</span>
      <span className="sg-banner__note">
        页面所有数据取自 contracts/ 下 v1 与 v1.1 契约的合成 example，不代表真实论文，也不代表任何已实现的能力。
      </span>
    </div>
  );
}
