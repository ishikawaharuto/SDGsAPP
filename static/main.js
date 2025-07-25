// static/main.js
// グラフのインスタンスを保持する変数
let monthlyChartInstance;
let activityChartInstance;

// データを取得してグラフを更新する関数
async function fetchAndUpdateCharts() {
    const response = await fetch('/api/activities');
    const data = await response.json();

    // 月間グラフの描画
    const monthlyCtx = document.getElementById('monthlyChart').getContext('2d');
    if (monthlyChartInstance) monthlyChartInstance.destroy(); // 既存のグラフを破棄
    monthlyChartInstance = new Chart(monthlyCtx, {
        type: 'bar',
        data: {
            labels: Object.keys(data.monthly_summary),
            datasets: [{
                label: 'CO2 (g)',
                data: Object.values(data.monthly_summary),
                backgroundColor: 'rgba(54, 162, 235, 0.6)'
            }]
        }
    });

    // 活動別グラフの描画
    const activityCtx = document.getElementById('activityChart').getContext('2d');
    if (activityChartInstance) activityChartInstance.destroy(); // 既存のグラフを破棄
    activityChartInstance = new Chart(activityCtx, {
        type: 'pie',
        data: {
            labels: Object.keys(data.activity_summary),
            datasets: [{
                data: Object.values(data.activity_summary),
            }]
        }
    });
}

// フォームの送信イベントを処理
document.getElementById('activityForm').addEventListener('submit', async (e) => {
    e.preventDefault(); // デフォルトの送信動作をキャンセル

    const newActivity = {
        activity_date: document.getElementById('activity_date').value,
        activity_type: document.getElementById('activity_type').value,
        duration: parseFloat(document.getElementById('duration').value),
        device: document.getElementById('device').value,
    };

    // APIにPOSTリクエストを送信
    await fetch('/api/activities', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newActivity)
    });

    // フォームをリセット
    e.target.reset();

    // グラフを更新
    fetchAndUpdateCharts();
});

// ページ読み込み時にグラフを初回描画
window.onload = fetchAndUpdateCharts;
