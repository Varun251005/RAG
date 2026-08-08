export interface TTSVoice {
  name: string;
  short_name: string;
  gender: string;
  locale: string;
}

export interface TTSVoicesResponse {
  voices: TTSVoice[];
  total: number;
}
