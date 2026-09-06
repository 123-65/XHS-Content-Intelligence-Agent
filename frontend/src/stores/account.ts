import { defineStore } from 'pinia'
import { accountProfile } from '@/mock/account'
import type { AccountProfile } from '@/types/account'

export const useAccountStore = defineStore('account', {
  state: () => ({
    profile: { ...accountProfile } as AccountProfile
  }),
  actions: {
    saveProfile(profile: AccountProfile) {
      this.profile = { ...profile }
    },
    resetProfile() {
      this.profile = { ...accountProfile }
    }
  }
})
