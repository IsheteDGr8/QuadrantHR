"use client"

import { create } from "zustand"

interface CanvasState {
  open: boolean
  width: number
  serverBlockCount: number
  setOpen: (open: boolean) => void
  toggle: () => void
  setWidth: (width: number) => void
  setServerBlockCount: (count: number) => void
}

const CANVAS_DEFAULT = 440
const CANVAS_MIN = 320
const CANVAS_MAX = 720

export const useCanvas = create<CanvasState>((set) => ({
  open: false,
  width: CANVAS_DEFAULT,
  serverBlockCount: 0,
  setOpen: (open) => set({ open }),
  toggle: () => set((state) => ({ open: !state.open })),
  setWidth: (width) => set({ width: Math.min(CANVAS_MAX, Math.max(CANVAS_MIN, width)) }),
  setServerBlockCount: (serverBlockCount) => set({ serverBlockCount }),
}))

export const CANVAS_WIDTH_BOUNDS = { min: CANVAS_MIN, max: CANVAS_MAX, default: CANVAS_DEFAULT }
