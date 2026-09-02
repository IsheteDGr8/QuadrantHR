"use client"

import type { ReactNode } from "react"
import { Check } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"

interface OptionMenuProps {
  trigger: ReactNode
  label?: string
  options: string[]
  value: string
  onChange: (value: string) => void
  align?: "start" | "center" | "end"
  side?: "top" | "bottom"
}

export function OptionMenu({
  trigger,
  label,
  options,
  value,
  onChange,
  align = "start",
  side = "bottom",
}: OptionMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{trigger}</DropdownMenuTrigger>
      <DropdownMenuContent
        align={align}
        side={side}
        className="min-w-[200px] border-border bg-popover text-foreground shadow-lg duration-300 ease-[cubic-bezier(0.22,1,0.36,1)]"
      >
        {label && <DropdownMenuLabel className="text-xs text-muted-foreground">{label}</DropdownMenuLabel>}
        {label && <DropdownMenuSeparator className="bg-border" />}
        {options.map((option) => {
          const selected = value === option
          return (
            <DropdownMenuItem
              key={option}
              onSelect={() => onChange(option)}
              className={cn(
                "flex items-center justify-between gap-2 text-[13px] text-foreground",
                "focus:bg-accent focus:text-foreground",
                "data-[highlighted]:bg-accent data-[highlighted]:text-foreground",
                selected && "bg-secondary/80 font-medium text-foreground",
              )}
            >
              {option}
              {selected && <Check className="h-3.5 w-3.5 text-primary" />}
            </DropdownMenuItem>
          )
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
