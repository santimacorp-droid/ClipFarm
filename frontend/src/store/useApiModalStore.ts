import { create } from 'zustand'

export interface OpenApiModalOptions {
  title?: string
  description?: string
  onSuccess?: () => void
}

export interface ApiModalStore {
  isOpen: boolean
  title?: string
  description?: string
  onSuccessCallback?: () => void
  openModal: (options?: OpenApiModalOptions) => void
  closeModal: () => void
  triggerSuccess: () => void
}

export const useApiModalStore = create<ApiModalStore>((set, get) => ({
  isOpen: false,
  title: undefined,
  description: undefined,
  onSuccessCallback: undefined,

  openModal: (options) => {
    set({
      isOpen: true,
      title: options?.title,
      description: options?.description,
      onSuccessCallback: options?.onSuccess,
    })
  },

  closeModal: () => {
    set({
      isOpen: false,
      title: undefined,
      description: undefined,
      onSuccessCallback: undefined,
    })
  },

  triggerSuccess: () => {
    const callback = get().onSuccessCallback
    set({
      isOpen: false,
      title: undefined,
      description: undefined,
      onSuccessCallback: undefined,
    })
    if (callback) {
      try {
        callback()
      } catch (err) {
        console.error('Failed to run onApiSuccess callback:', err)
      }
    }
  },
}))
