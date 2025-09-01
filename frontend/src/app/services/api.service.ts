import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({ providedIn: 'root' })
export class ApiService {
  base = (window as any).__API__ || 'http://127.0.0.1:8100';
  constructor(private http: HttpClient) {}

  start() { return this.http.post(this.base + '/bot/start', {}); }
  stop()  { return this.http.post(this.base + '/bot/stop', {}); }
  status(){ return this.http.get(this.base + '/bot/status'); }
  scan()  { return this.http.post(this.base + '/scanner/scan', {}); }
  getConfig(){ return this.http.get(this.base + '/config'); }
  putConfig(cfg:any){ return this.http.put(this.base + '/config', { cfg }); }
}
