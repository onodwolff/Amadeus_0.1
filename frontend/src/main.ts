// включаем зону, чтобы отрисовка и детект изменений точно работали
import 'zone.js';

import { bootstrapApplication } from '@angular/platform-browser';
import { provideAnimations } from '@angular/platform-browser/animations';
import { AppComponent } from './app/app.component';
import { provideHttpClient, withFetch } from '@angular/common/http';

// минимально-необходимые провайдеры на весь апп
bootstrapApplication(AppComponent, {
  providers: [
    provideHttpClient(withFetch()),
    provideAnimations(),
  ],
}).catch(err => console.error(err));
