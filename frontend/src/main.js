import './app.css';
import App from './App.svelte';

const target = document.getElementById('app');
if (target) {
  target.innerHTML = '';
}

const app = new App({
  target: target
});

export default app;
