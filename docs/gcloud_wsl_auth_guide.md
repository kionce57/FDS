# 解決 WSL 環境下 gcloud auth application-default login 失敗指南

本文件記錄了在 WSL (Windows Subsystem for Linux) 環境中配置 Google Cloud `application-default` 憑證時遇到的問題、原因分析及最終解決方案。

## 1. 問題描述

在嘗試取得 Access Token 時遇到報錯：

```bash
$ gcloud auth application-default print-access-token
WARNING: Compute Engine Metadata server unavailable on attempt 1 of 3. Reason: timed out
...
ERROR: (gcloud.auth.application-default.print-access-token) Your default credentials were not found.
```

**原因**：
`gcloud` 在本地找不到憑證檔案，且因為不是在 GCP 運算實例上執行，無法連線到 Metadata Server。

## 2. 嘗試解決與遇到的新問題

嘗試執行標準登入指令：
```bash
gcloud auth application-default login
```
**結果**：因為 WSL 是無介面環境 (Headless)，無法透過 CLI 自動開啟瀏覽器。

接著嘗試使用 `--no-browser` 參數 (舊式方法)：
```bash
gcloud auth application-default login --no-browser
```
**結果**：複製網址到瀏覽器後，Google 回傳錯誤：
> **已封鎖存取權：授權錯誤**
> Error 400: invalid_request
> Missing required parameter: redirect_uri

**原因**：
Google 為了安全性，已經**棄用 (Deprecated)** 了舊式的 Out-of-Band (OOB) 驗證流程（即「複製貼上授權碼」的方式）。現在 OAuth 請求必須包含 `redirect_uri`。

## 3. 最終解決方案

在 WSL 環境中，應使用 `--no-launch-browser` 參數。

### 操作步驟

1.  **在 WSL 終端機執行**：
    ```bash
    gcloud auth application-default login --no-launch-browser
    ```
    *(注意：是 `no-launch-browser` 而不是 `no-browser`)*

2.  **複製生成的網址**：
    終端機顯示的網址現在會包含 `redirect_uri=http://localhost...`。

3.  **在 Windows 瀏覽器開啟**：
    將網址貼到 Windows 的 Chrome/Edge 中並完成登入授權。

4.  **自動完成**：
    授權後，瀏覽器會重定向到 localhost。由於 **WSL 2 與 Windows 共享 localhost 网络端口**，WSL 中的 `gcloud` 能夠接收到回傳的授權資訊並自動完成設定。

### 驗證

再次執行以下指令確認憑證已設定成功：
```bash
gcloud auth application-default print-access-token
```
