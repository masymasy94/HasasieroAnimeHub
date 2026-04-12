export interface Settings {
  download_dir: string;
  host_download_path: string;
  max_concurrent_downloads: number;
  telegram_bot_token: string;
  telegram_chat_id: string;
}

export interface SettingsUpdate {
  download_dir?: string;
  max_concurrent_downloads?: number;
  telegram_bot_token?: string;
  telegram_chat_id?: string;
}
