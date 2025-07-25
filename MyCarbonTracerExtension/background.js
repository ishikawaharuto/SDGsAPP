const PING_INTERVAL_MINUTES = 5; // 5分おきにサーバーへ送信
let activityLog = {}; // { 'domain.com': 120 (seconds), ... }

// 1秒ごとにアクティブなタブのドメインを記録
setInterval(async () => {
  try {
    const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    if (tab && tab.url && tab.status === 'complete') {
      const url = new URL(tab.url);
      // http/httpsプロトコルのページのみを対象
      if (url.protocol === "http:" || url.protocol === "https:" || url.protocol === "https") {
        const domain = url.hostname;
        activityLog[domain] = (activityLog[domain] || 0) + 1;
      }
    }
  } catch (error) {
    // console.error("Error tracking tab:", error);
  }
}, 1000);

// アラーム（定期実行）の設定
chrome.alarms.create('sendData', { periodInMinutes: PING_INTERVAL_MINUTES });

// アラーム発火時の処理
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === 'sendData' && Object.keys(activityLog).length > 0) {
    
    const { apiKey } = await chrome.storage.sync.get(['apiKey']);
    if (!apiKey) {
      console.log("API Key not set. Aborting send.");
      return;
    }
    
    const currentLog = activityLog;
    activityLog = {}; // ログをリセット

    const API_ENDPOINT = 'https://あなたのアプリ名.onrender.com/api/log_from_extension'; // ★★★自分のRenderアプリのURLに書き換える★★★

    for (const domain in currentLog) {
      const duration_seconds = currentLog[domain];
      if (duration_seconds > 0) {
        try {
          await fetch(API_ENDPOINT, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-API-KEY': apiKey,
            },
            body: JSON.stringify({
              domain: domain,
              duration_minutes: duration_seconds / 60.0,
            }),
          });
        } catch (e) {
          console.error("Failed to send data:", e);
          // 送信失敗したデータは次回に持ち越す
          activityLog[domain] = (activityLog[domain] || 0) + duration_seconds;
        }
      }
    }
  }
});
