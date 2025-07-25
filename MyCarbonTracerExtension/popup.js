const apiKeyInput = document.getElementById('apiKey');
const saveButton = document.getElementById('saveButton');
const statusEl = document.getElementById('status');

// 保存されているAPIキーを読み込んで表示
chrome.storage.sync.get(['apiKey'], (result) => {
  if (result.apiKey) {
    apiKeyInput.value = result.apiKey;
  }
});

// 保存ボタンのクリックイベント
saveButton.addEventListener('click', () => {
  const apiKey = apiKeyInput.value;
  if (apiKey) {
    chrome.storage.sync.set({ apiKey: apiKey }, () => {
      statusEl.textContent = 'APIキーを保存しました！';
      setTimeout(() => { statusEl.textContent = ''; }, 2000);
    });
  }
});
