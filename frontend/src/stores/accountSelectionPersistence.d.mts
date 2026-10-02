type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>

export const ACCOUNT_SELECTION_STORAGE_KEY: string
export function readPersistedAccountRef(storage?: StorageLike | null): number | null
export function persistAccountRef(accountRef: number | null, storage?: StorageLike | null): void
export function isMissingOrForbiddenAccountContext(error: unknown): boolean
