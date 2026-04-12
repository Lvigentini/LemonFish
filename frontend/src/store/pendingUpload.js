/**
 * Pending upload store
 * Holds files + simulation requirement before the Process page takes over.
 *
 * Phase 7: persists metadata (filenames, requirement) across page refreshes
 * via localStorage. File objects themselves cannot be serialized, so after a
 * refresh the user is prompted to re-select their files — the requirement
 * text and filename list are restored automatically.
 */
import { reactive, watch } from 'vue'

const STORAGE_KEY = 'lemonfish_pending_upload'

// Restore from localStorage if present. Files will always be empty after refresh.
function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw)
  } catch (e) {
    console.warn('Failed to load pending upload from storage:', e)
    return null
  }
}

const saved = loadFromStorage()

const state = reactive({
  files: [],  // File[] — live objects, lost on refresh
  fileNames: saved?.fileNames || [],  // string[] — persisted for display
  simulationRequirement: saved?.simulationRequirement || '',
  isPending: saved?.isPending || false,
  restoredFromStorage: !!saved,  // true if we loaded from storage this session
})

// Persist metadata (NOT files) whenever state changes.
watch(
  () => ({
    simulationRequirement: state.simulationRequirement,
    fileNames: state.fileNames,
    isPending: state.isPending,
  }),
  (val) => {
    try {
      if (val.isPending) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(val))
      } else {
        localStorage.removeItem(STORAGE_KEY)
      }
    } catch (e) {
      console.warn('Failed to persist pending upload:', e)
    }
  },
  { deep: true }
)

export function setPendingUpload(files, requirement) {
  state.files = files
  state.fileNames = files.map(f => f.name || 'unnamed')
  state.simulationRequirement = requirement
  state.isPending = true
  state.restoredFromStorage = false
}

export function getPendingUpload() {
  return {
    files: state.files,
    fileNames: state.fileNames,
    simulationRequirement: state.simulationRequirement,
    isPending: state.isPending,
    restoredFromStorage: state.restoredFromStorage,
    // True if we have filenames but no actual File objects — user must re-select
    needsRefileUpload: state.restoredFromStorage && state.files.length === 0 && state.fileNames.length > 0,
  }
}

export function clearPendingUpload() {
  state.files = []
  state.fileNames = []
  state.simulationRequirement = ''
  state.isPending = false
  state.restoredFromStorage = false
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch (e) {
    // ignore
  }
}

export default state
