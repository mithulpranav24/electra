import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

document.querySelectorAll<HTMLMetaElement>('meta[property="og:image"], meta[name="twitter:image"]').forEach((meta) => {
  meta.content = new URL('/og.png', window.location.origin).href
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
