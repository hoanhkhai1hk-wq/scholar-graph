import { ApiFetchError } from "@/lib/api";
import Diagnostics from "./Diagnostics";

/**
 * 明确的错误态：显示接口地址、状态码、原因。
 * 接口不通时绝不允许静默回落到任何假数据。
 */
export default function ErrorState({
  title,
  error,
}: {
  title: string;
  error: unknown;
}) {
  if (error instanceof ApiFetchError) {
    return (
      <div className="sg-error" role="alert">
        <div className="sg-error__title">{title}</div>
        <p>{error.status === 0 ? "无法连接研究服务，请检查网络或服务状态后重试。" : error.detail}</p>
        <Diagnostics summary="错误诊断（接口与响应状态）"><dl className="sg-kv">
          <dt>接口地址</dt>
          <dd className="sg-mono">{error.url}</dd>
          <dt>状态码</dt>
          <dd className="sg-mono">
            {error.status === 0 ? "无响应" : String(error.status)}
          </dd>
          <dt>错误码</dt>
          <dd className="sg-mono">{error.errorCode}</dd>
          <dt>原因</dt>
          <dd>{error.detail}</dd>
        </dl></Diagnostics>
        <p className="sg-error__hint">
          后端未返回数据，页面不显示任何替代数据。请确认后端已启动且地址一致。
        </p>
      </div>
    );
  }

  return (
    <div className="sg-error" role="alert">
      <div className="sg-error__title">{title}</div>
      <p>当前内容读取失败，请检查服务状态后重试。</p>
      <Diagnostics summary="错误诊断"><p>{error instanceof Error ? error.message : String(error)}</p></Diagnostics>
      <p className="sg-error__hint">
        后端未返回数据，页面不显示任何替代数据。
      </p>
    </div>
  );
}
