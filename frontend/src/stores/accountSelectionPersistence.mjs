export const ACCOUNT_SELECTION_STORAGE_KEY = 'xhs-growth:selected-account-ref'

const browserStorage = () => typeof window === 'undefined' ? null : window.localStorage

export const readPersistedAccountRef = (storage = browserStorage()) => {
  if (!storage) return null
  const raw = storage.getItem(ACCOUNT_SELECTION_STORAGE_KEY)
  if (raw === null) return null
  const accountRef = Number(raw)
  if (!Number.isSafeInteger(accountRef) || accountRef <= 0 || String(accountRef) !== raw) {
    storage.removeItem(ACCOUNT_SELECTION_STORAGE_KEY)
    return null
  }
  return accountRef
}

export const persistAccountRef = (accountRef, storage = browserStorage()) => {
  if (!storage) return
  if (accountRef === null) {
    storage.removeItem(ACCOUNT_SELECTION_STORAGE_KEY)
    return
  }
  if (!Number.isSafeInteger(accountRef) || accountRef <= 0) {
    storage.removeItem(ACCOUNT_SELECTION_STORAGE_KEY)
    return
  }
  storage.setItem(ACCOUNT_SELECTION_STORAGE_KEY, String(accountRef))
}

export const isMissingOrForbiddenAccountContext = (error) => {
  const status = error?.response?.status
  return status === 403 || status === 404
}
