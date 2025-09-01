import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class ScriptLoaderService {
    private cache = new Map<string, Promise<void>>();

    load(url: string, id?: string): Promise<void> {
        if (this.cache.has(url)) return this.cache.get(url)!;

        const p = new Promise<void>((resolve, reject) => {
            // если уже есть в DOM — резолвнем сразу
            if (id && document.getElementById(id)) { resolve(); return; }
            const s = document.createElement('script');
            s.src = url;
            s.async = true;
            if (id) s.id = id;
            s.onload = () => resolve();
            s.onerror = () => reject(new Error(`Failed to load: ${url}`));
            document.body.appendChild(s);
        });

        this.cache.set(url, p);
        return p;
    }
}
