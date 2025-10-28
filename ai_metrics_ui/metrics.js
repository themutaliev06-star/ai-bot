const $ = (id) => document.getElementById(id);
const fmt = (n, d=2) => {
  if (n === null || n === undefined || isNaN(n)) return "—";
  return Number(n).toLocaleString(undefined, {maximumFractionDigits: d});
};

async function fetchMetrics() {
  const url = "http://127.0.0.1:8800/proxy/ai/metrics";
  try {
    const res = await fetch(url, {cache: "no-store"});
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    const m = data.metrics || {};
    $("equity").textContent = fmt(m.equity, 2);
    $("pnl_total").textContent = fmt(m.pnl_total, 2);
    $("pnl_day").textContent = fmt(m.pnl_day, 2);
    $("sharpe").textContent = fmt(m.sharpe, 2);
    $("win_rate").textContent = fmt(Number(m.win_rate)*100, 1) + "%";
    $("trades_count").textContent = fmt(m.trades_count, 0);
    $("episode").textContent = fmt(m.episode, 0);
    $("avg_reward").textContent = fmt(m.avg_reward, 3);
    $("timestamp").textContent = "Updated: " + (m.timestamp || new Date().toISOString());
    const st = document.getElementById("status");
    st.textContent = "OK";
    st.classList.remove("fail"); st.classList.add("ok");
  } catch (e) {
    const st = document.getElementById("status");
    st.textContent = "FAIL";
    st.classList.remove("ok"); st.classList.add("fail");
  }
}

fetchMetrics();
setInterval(fetchMetrics, 2000);