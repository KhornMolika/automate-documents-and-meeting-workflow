export function formatDate(value: string | Date) {
  return new Date(value).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

export function formatTime(value: string | Date) {
  return new Date(value).toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatTimeRange(start: string | Date, end: string | Date) {
  return `${formatTime(start)}–${formatTime(end)}`
}

export function formatBytes(value?: number | null) {
  if (value === null || value === undefined) return '—'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

export function fileType(value?: string | null) {
  if (!value) return 'FILE'
  return value.split('.').pop()?.toUpperCase() ?? 'FILE'
}

export function statusTone(status: string) {
  if (status === 'Completed' || status === 'Verified' || status === 'Published') return 'positive'
  if (status === 'Overdue' || status === 'Cancelled' || status === 'Failed' || status === 'Transcription failed') return 'negative'
  if (status === 'Draft' || status === 'Processing' || status === 'Due soon') return 'warning'
  return 'outline'
}

export function statusLabel(status: string) {
  return status
}

export function initials(name?: string | null) {
  if (!name) return 'AU'
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map(part => part[0]?.toUpperCase() ?? '')
    .join('')
}

export function parseDiscussionPoints(value?: string | null): string[] {
  if (!value) return []
  try {
    const parsed = JSON.parse(value)
    return Array.isArray(parsed) ? parsed.map(String) : []
  } catch {
    return []
  }
}

export function parseEntities(value?: string | null): { label: string, values: string[] }[] {
  if (!value) return []
  try {
    const parsed = JSON.parse(value)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return []
    return Object.entries(parsed)
      .map(([label, item]) => {
        const values = Array.isArray(item)
          ? item
              .map(entry => (typeof entry === 'string' ? entry : JSON.stringify(entry)))
              .filter(Boolean)
          : [typeof item === 'string' ? item : JSON.stringify(item)]
        return {
          label: label.replaceAll('_', ' '),
          values: values.filter(value => value && value !== 'null'),
        }
      })
      .filter(entity => entity.values.length > 0)
  } catch {
    return []
  }
}


export function plural(count: number, singular: string, pluralForm?: string) {
  return `${count} ${count === 1 ? singular : (pluralForm ?? `${singular}s`)}`
}
