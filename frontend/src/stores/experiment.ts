import { defineStore } from 'pinia'
import { competitorAnalysisReport, draft, experiments, reviewReport } from '@/mock/experiments'
import type { Draft, ReviewReport } from '@/types/draft'
import type { Experiment } from '@/types/experiment'

export const useExperimentStore = defineStore('experiment', {
  state: () => ({
    experiments: [...experiments] as Experiment[],
    selectedExperimentId: 'exp-001',
    draft: { ...draft } as Draft,
    reviewReport: { ...reviewReport } as ReviewReport,
    analysisReport: competitorAnalysisReport,
    demoPublishUrl: '',
    reviewGenerated: false,
    draftGenerated: false
  }),
  getters: {
    selectedExperiment: (state) => state.experiments.find((item) => item.id === state.selectedExperimentId) || state.experiments[0]
  },
  actions: {
    createFromAnalysis() {
      this.selectedExperimentId = 'exp-001'
      const target = this.experiments.find((item) => item.id === 'exp-001')
      if (target) target.status = 'DRAFT'
    },
    markDraftGenerated() {
      this.draftGenerated = true
      const target = this.experiments.find((item) => item.id === this.selectedExperimentId)
      if (target) target.status = 'READY'
    },
    markReviewed() {
      this.reviewGenerated = true
    },
    savePublishUrl(url: string) {
      this.demoPublishUrl = url
      const target = this.experiments.find((item) => item.id === this.selectedExperimentId)
      if (target) {
        target.published = true
        target.status = 'PUBLISHED'
        target.publishUrl = url
        target.publishedAt = '2026-09-06 20:30'
      }
    },
    markAnalyzed(value: number) {
      const target = this.experiments.find((item) => item.id === this.selectedExperimentId)
      if (target) {
        target.status = 'ANALYZED'
        target.businessValue = value
      }
    }
  }
})
