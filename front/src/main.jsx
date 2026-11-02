import React from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@fontsource/unbounded/latin-700.css'
import './styles/tokens.css'
import './styles/app.css'
import './styles/workspace.css'
import './styles/settings.css'
import App from './App'
import NoteEditor from './notes/NoteEditor'
import RecipeCanvas from './recipe/RecipeCanvas'
import { RECIPE_ON } from './components/SkillReports'

// #/notes/<jobId> opens the note editor in its own tab, #/recipe/<jobId> the 抄作业 node canvas;
// everything else is the workbench. With 抄作业 off (no VITE_RECIPE=1) the canvas link opens the workbench.
const note = /^#\/notes\/([\w-]+)/.exec(window.location.hash)
const graph = RECIPE_ON && /^#\/recipe\/([\w-]+)/.exec(window.location.hash)
createRoot(document.getElementById('root')).render(
  note ? <NoteEditor jobId={note[1]} /> : graph ? <RecipeCanvas jobId={graph[1]} /> : <App />)
