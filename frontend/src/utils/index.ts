import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { formatDistanceToNow, format } from 'date-fns'
import type { IncidentSeverity, IncidentStatus, NotificationStatus } from '@/types'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// ---- Date formatting --------------------------------------------------------------------------------------------------------------------

export function timeAgo(date: string | Date | null | undefined): string {
  if (!date) return 'unknown'
  const d = new Date(date)
  if (isNaN(d.getTime())) return 'unknown'
  return formatDistanceToNow(d, { addSuffix: true })
}

export function formatDate(date: string | Date | null | undefined, fmt = 'MMM dd, yyyy HH:mm'): string {
  if (!date) return '—'
  const d = new Date(date)
  if (isNaN(d.getTime())) return '—'
  return format(d, fmt)
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  return `${(seconds / 3600).toFixed(1)}h`
}

// ---- Severity helpers ------------------------------------------------------------------------------------------------------------------

// Keys must match backend IncidentSeverity enum (lowercase)
export const SEVERITY_CONFIG: Record<IncidentSeverity, {
  label: string; color: string; bg: string; border: string; dot: string
}> = {
  critical: { label: 'CRITICAL', color: 'text-red-400',    bg: 'bg-red-500/10',    border: 'border-red-500/30',    dot: 'bg-red-500' },
  high:     { label: 'HIGH',     color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/30', dot: 'bg-orange-500' },
  medium:   { label: 'MEDIUM',   color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', dot: 'bg-yellow-400' },
  low:      { label: 'LOW',      color: 'text-green-400',  bg: 'bg-green-500/10',  border: 'border-green-500/30',  dot: 'bg-green-500' },
  info:     { label: 'INFO',     color: 'text-blue-400',   bg: 'bg-blue-500/10',   border: 'border-blue-500/30',   dot: 'bg-blue-400' },
}

// Keys must match backend IncidentStatus enum: new/triaging/contained/eradicating/recovering/closed/reopened
export const STATUS_CONFIG: Record<IncidentStatus, {
  label: string; color: string; bg: string
}> = {
  new:         { label: 'New',         color: 'text-red-400',    bg: 'bg-red-500/10' },
  triaging:    { label: 'Triaging',    color: 'text-orange-400', bg: 'bg-orange-500/10' },
  contained:   { label: 'Contained',   color: 'text-blue-400',   bg: 'bg-blue-500/10' },
  eradicating: { label: 'Eradicating', color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  recovering:  { label: 'Recovering',  color: 'text-purple-400', bg: 'bg-purple-500/10' },
  closed:      { label: 'Closed',      color: 'text-green-400',  bg: 'bg-green-500/10' },
  reopened:    { label: 'Reopened',    color: 'text-red-300',    bg: 'bg-red-500/20' },
}

// Must match backend notification status values: pending/approved/sent/failed
export const NOTIF_STATUS_CONFIG: Record<NotificationStatus, {
  label: string; color: string; bg: string
}> = {
  pending:  { label: 'Pending',  color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  approved: { label: 'Approved', color: 'text-blue-400',   bg: 'bg-blue-500/10' },
  sent:     { label: 'Sent',     color: 'text-green-400',  bg: 'bg-green-500/10' },
  failed:   { label: 'FAILED',   color: 'text-red-400',    bg: 'bg-red-500/20' },
}

export const JURISDICTION_CONFIG = {
  GDPR: { label: 'GDPR', color: 'text-blue-400', flag: '🇪🇺', hours: 72 },
  HIPAA: { label: 'HIPAA', color: 'text-purple-400', flag: '🇺🇸', hours: 60 * 24 },
  DPDPA: { label: 'DPDPA', color: 'text-orange-400', flag: '🇮🇳', hours: 72 },
}

// ---- Misc ------------------------------------------------------------------------------------------------------------------------------------------

export function truncate(str: string, n: number): string {
  if (str.length <= n) return str
  return str.slice(0, n) + '…'
}

export function shortHash(hash: string): string {
  if (!hash || hash.length < 16) return hash ?? ''
  return `${hash.slice(0, 8)}…${hash.slice(-8)}`
}
