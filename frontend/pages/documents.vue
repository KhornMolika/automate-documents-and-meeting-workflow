<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  Archive,
  Download,
  ExternalLink,
  FileText,
  Link2,
  MoreHorizontal,
  Pencil,
  RotateCcw,
  Search,
  Trash2,
  Upload,
} from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Badge } from '~/components/ui/badge'
import { Button } from '~/components/ui/button'
import { Card, CardDescription, CardHeader, CardTitle } from '~/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '~/components/ui/dialog'
import { Input } from '~/components/ui/input'
import { Label } from '~/components/ui/label'
import { Select } from '~/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '~/components/ui/table'
import EmptyState from '~/components/workspace/EmptyState.vue'
import ErrorState from '~/components/workspace/ErrorState.vue'
import LoadingState from '~/components/workspace/LoadingState.vue'
import PageHeader from '~/components/workspace/PageHeader.vue'
import { useApi } from '~/composables/useApi'
import { useAuth } from '~/composables/useAuth'
import { fileType, formatBytes, formatDate, parseEntities, plural } from '~/lib/format'
import type { Category, WorkspaceDocument } from '~/types/api'

useHead({ title: 'Documents · ACLEDA University' })

const api = useApi()
const { user } = useAuth()
const { data: categoryData } = await useAsyncData('document-categories', () => api<Category[]>('/documents/categories'))
const { data: documentData, pending, error, refresh } = await useAsyncData('documents', () =>
  api<WorkspaceDocument[]>('/documents', { query: { limit: 200, include_archived: true } }),
)

const categories = computed(() => categoryData.value ?? [])
const allDocuments = computed(() => documentData.value ?? [])
const showArchived = ref(false)
const search = ref('')
const debouncedSearch = ref('')
let searchTimer: ReturnType<typeof setTimeout> | null = null
const { data: searchData, pending: searchPending, refresh: refreshSearch } = await useAsyncData(
  'document-search',
  () => debouncedSearch.value
    ? api<{ items: WorkspaceDocument[], total: number }>('/documents/search', {
        query: { q: debouncedSearch.value, include_archived: true },
      })
    : Promise.resolve(null),
  { watch: [debouncedSearch] },
)
const sourceDocuments = computed(() =>
  debouncedSearch.value ? (searchData.value?.items ?? []) : allDocuments.value,
)
const documents = computed(() =>
  sourceDocuments.value.filter(document => document.is_archived === showArchived.value),
)
const archivedCount = computed(() => allDocuments.value.filter(document => document.is_archived).length)
const departmentName = computed(() => user.value?.department?.name ?? 'Department workspace')

async function refreshDocuments() {
  await refresh()
  if (debouncedSearch.value) await refreshSearch()
}

watch(search, (value) => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    debouncedSearch.value = value.trim()
  }, 300)
})

const category = ref('ALL')
const year = ref('ALL')
const selected = ref<WorkspaceDocument | null>(null)
const openMenuId = ref('')
const actionBusyId = ref('')
const renameOpen = ref(false)
const renameTarget = ref<WorkspaceDocument | null>(null)
const renameTitle = ref('')
const renaming = ref(false)
const deleteOpen = ref(false)
const deleteTarget = ref<WorkspaceDocument | null>(null)
const deleting = ref(false)
const versionOpen = ref(false)
const versionTarget = ref<WorkspaceDocument | null>(null)
const versionFile = ref<File | null>(null)
const versionUploading = ref(false)
const summaryLanguage = ref<'en' | 'km'>('en')
const summaryDraftLanguage = ref<'en' | 'km' | null>(null)
const uploadOpen = ref(false)
const uploading = ref(false)
const summarizing = ref(false)
const uploadMode = ref<'file' | 'google'>('file')
const uploadForm = ref({
  title: '',
  category_id: 'NONE',
  year: '2026–2027',
  file: null as File | null,
  googleUrl: '',
})

const years = computed(() => [...new Set(documents.value.map(document => document.academic_year))].sort().reverse())
const categoryOptions = computed(() => [
  { value: 'ALL', label: 'All categories' },
  ...categories.value.map(item => ({ value: item.id, label: item.name })),
])
const yearOptions = computed(() => [
  { value: 'ALL', label: 'All years' },
  ...years.value.map(item => ({ value: item, label: item })),
])
const uploadCategoryOptions = computed(() => [
  { value: 'NONE', label: 'Uncategorised' },
  ...categories.value.map(item => ({ value: item.id, label: item.name })),
])

const filteredDocuments = computed(() =>
  documents.value.filter(document =>
    (category.value === 'ALL' || document.category?.id === category.value)
    && (year.value === 'ALL' || document.academic_year === year.value),
  ),
)

const categoryRows = computed(() => {
  const rows = new Map<string, { key: string, label: string, count: number }>()
  for (const item of categories.value) {
    rows.set(item.id, { key: item.id, label: item.name, count: 0 })
  }
  for (const document of documents.value) {
    const key = document.category?.id ?? 'uncategorised'
    const label = document.category?.name ?? 'Uncategorised'
    const row = rows.get(key) ?? { key, label, count: 0 }
    row.count += 1
    rows.set(key, row)
  }
  return [...rows.values()]
})

const storageUsed = computed(() =>
  documents.value.reduce((total, document) => total + (document.latest_version?.file_size_bytes ?? 0), 0),
)

const largestFile = computed(() =>
  documents.value.reduce((max, document) => Math.max(max, document.latest_version?.file_size_bytes ?? 0), 0),
)

const oldestRecord = computed(() => {
  const dates = documents.value.map(document => new Date(document.created_at).getTime())
  return dates.length ? formatDate(new Date(Math.min(...dates))) : '—'
})

const lastUpdate = computed(() => {
  const dates = documents.value.map(document => new Date(document.updated_at).getTime())
  return dates.length ? formatDate(new Date(Math.max(...dates))) : '—'
})

const selectedSummary = computed(() => selected.value?.latest_version?.abstract_summary ?? '')
const selectedEntities = computed(() => parseEntities(selected.value?.latest_version?.extracted_entities))
const selectedVersions = computed(() => selected.value?.versions ?? [])

function textHasKhmer(value: string | null | undefined) {
  return /[\u1780-\u17FF]/.test(value ?? '')
}

function openDocument(document: WorkspaceDocument) {
  closeMenu()
  selected.value = document
  const existingSummary = document.latest_version?.abstract_summary ?? ''
  summaryLanguage.value = document.latest_version?.contains_khmer ? 'km' : 'en'
  summaryDraftLanguage.value = existingSummary
    ? (textHasKhmer(existingSummary) ? 'km' : 'en')
    : null
}

function onFile(event: Event) {
  const input = event.target as HTMLInputElement
  uploadForm.value.file = input.files?.[0] ?? null
}

function openGoogleDrive() {
  window.open('https://drive.google.com/drive/search', '_blank', 'noopener,noreferrer')
}

function resetUpload() {
  uploadMode.value = 'file'
  uploadForm.value = {
    title: '',
    category_id: 'NONE',
    year: '2026–2027',
    file: null,
    googleUrl: '',
  }
}

async function addDocument() {
  if (uploadMode.value === 'file' && !uploadForm.value.file) {
    toast.error('Choose a file first.')
    return
  }
  if (uploadMode.value === 'google' && !uploadForm.value.googleUrl.trim()) {
    toast.error('Paste a Google Docs, Sheets, or Drive link first.')
    return
  }
  uploading.value = true
  try {
    let created: WorkspaceDocument
    if (uploadMode.value === 'google') {
      created = await api<WorkspaceDocument>('/documents/import/google', {
        method: 'POST',
        body: {
          url: uploadForm.value.googleUrl.trim(),
          title: uploadForm.value.title.trim() || undefined,
          category_id: uploadForm.value.category_id === 'NONE' ? undefined : uploadForm.value.category_id,
          academic_year: uploadForm.value.year,
        },
      })
    } else {
      const formData = new FormData()
      formData.append('file', uploadForm.value.file!)
      if (uploadForm.value.title.trim()) formData.append('title', uploadForm.value.title.trim())
      if (uploadForm.value.category_id && uploadForm.value.category_id !== 'NONE') {
        formData.append('category_id', uploadForm.value.category_id)
      }
      formData.append('academic_year', uploadForm.value.year)
      created = await api<WorkspaceDocument>('/documents/upload', {
        method: 'POST',
        body: formData,
      })
    }
    await refreshDocuments()
    uploadOpen.value = false
    resetUpload()
    toast.success(
      created.latest_version?.abstract_summary
        ? 'Document uploaded and summarized.'
        : 'Document uploaded. You can generate an optional summary from the document panel.',
    )
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Document upload failed.')
  } finally {
    uploading.value = false
  }
}

async function summarizeSelected() {
  if (!selected.value) return
  summarizing.value = true
  try {
    const language = summaryLanguage.value
    const updated = await api<WorkspaceDocument>(
      `/documents/${selected.value.id}/summarize?language=${language}`,
      { method: 'POST' },
    )
    selected.value = updated
    summaryDraftLanguage.value = language
    await refreshDocuments()
    toast.success(
      `Document summary generated in ${language === 'km' ? 'Khmer' : 'English'}.`,
    )
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Summary generation failed.')
  } finally {
    summarizing.value = false
  }
}

function toggleMenu(documentId: string) {
  openMenuId.value = openMenuId.value === documentId ? '' : documentId
}

function closeMenu() {
  openMenuId.value = ''
}

function openRename(document: WorkspaceDocument) {
  closeMenu()
  renameTarget.value = document
  renameTitle.value = document.title
  renameOpen.value = true
}

async function renameDocument() {
  const document = renameTarget.value
  const title = renameTitle.value.trim()
  if (!document || !title) {
    toast.error('Enter a document title.')
    return
  }
  renaming.value = true
  try {
    const updated = await api<WorkspaceDocument>(`/documents/${document.id}`, {
      method: 'PATCH',
      body: { title },
    })
    if (selected.value?.id === updated.id) selected.value = updated
    renameOpen.value = false
    renameTarget.value = null
    await refreshDocuments()
    toast.success('Document renamed.')
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not rename the document.')
  } finally {
    renaming.value = false
  }
}

function openDelete(document: WorkspaceDocument) {
  closeMenu()
  deleteTarget.value = document
  deleteOpen.value = true
}

async function deleteDocument() {
  const document = deleteTarget.value
  if (!document) return
  deleting.value = true
  try {
    await api(`/documents/${document.id}`, { method: 'DELETE' })
    if (selected.value?.id === document.id) selected.value = null
    deleteOpen.value = false
    deleteTarget.value = null
    await refreshDocuments()
    toast.success('Document deleted.')
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not delete the document.')
  } finally {
    deleting.value = false
  }
}

async function toggleArchive(document: WorkspaceDocument) {
  closeMenu()
  actionBusyId.value = document.id
  try {
    const updated = await api<WorkspaceDocument>(`/documents/${document.id}/archive`, {
      method: 'PATCH',
      body: { is_archived: !document.is_archived },
    })
    if (selected.value?.id === updated.id) selected.value = updated
    await refreshDocuments()
    toast.success(updated.is_archived ? 'Document archived.' : 'Document restored.')
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not update the document.')
  } finally {
    actionBusyId.value = ''
  }
}

function openVersion(document: WorkspaceDocument) {
  closeMenu()
  versionTarget.value = document
  versionFile.value = null
  versionOpen.value = true
}

function onVersionFile(event: Event) {
  const input = event.target as HTMLInputElement
  versionFile.value = input.files?.[0] ?? null
}

async function uploadVersion() {
  const document = versionTarget.value
  if (!document || !versionFile.value) {
    toast.error('Choose a file for the new version.')
    return
  }
  versionUploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', versionFile.value)
    const updated = await api<WorkspaceDocument>(`/documents/${document.id}/versions`, {
      method: 'POST',
      body: formData,
    })
    if (selected.value?.id === updated.id) selected.value = updated
    versionOpen.value = false
    versionTarget.value = null
    versionFile.value = null
    await refreshDocuments()
    toast.success(`Version ${updated.current_version} uploaded.`)
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not upload the new version.')
  } finally {
    versionUploading.value = false
  }
}

async function downloadDocument(document: WorkspaceDocument, versionId?: string) {
  closeMenu()
  actionBusyId.value = document.id
  try {
    const path = versionId
      ? `/documents/${document.id}/download?version_id=${encodeURIComponent(versionId)}`
      : `/documents/${document.id}/download`
    const blob = await api<Blob>(path, { responseType: 'blob' })
    const objectUrl = URL.createObjectURL(blob)
    const anchor = window.document.createElement('a')
    anchor.href = objectUrl
    anchor.download = versionId
      ? (selectedVersions.value.find(version => version.id === versionId)?.file_name ?? document.title)
      : (document.latest_version?.file_name ?? document.title)
    anchor.click()
    URL.revokeObjectURL(objectUrl)
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Download failed.')
  } finally {
    actionBusyId.value = ''
  }
}

onMounted(() => window.document.addEventListener('click', closeMenu))
onUnmounted(() => {
  window.document.removeEventListener('click', closeMenu)
  if (searchTimer) clearTimeout(searchTimer)
})
</script>

<template>
  <div>
    <PageHeader
      title="Documents"
      :description="`${plural(documents.length, 'document')} in ${departmentName}. Search titles, abstracts and extracted content.`"
    >
      <template #actions>
        <Button @click="uploadOpen = true">
          <Upload class="h-4 w-4" />
          Upload document
        </Button>
      </template>
    </PageHeader>

    <LoadingState v-if="pending || (searchPending && debouncedSearch)" class="mt-6" />
    <ErrorState v-else-if="error" class="mt-6" :message="error.message" @retry="refresh" />

    <template v-else>
      <div class="mt-6 flex flex-col gap-2 sm:flex-row sm:items-center">
        <div class="relative min-w-0 flex-1">
          <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            v-model="search"
            type="search"
            placeholder="Search documents"
            aria-label="Search documents"
            class="pl-9"
          />
        </div>
        <div class="grid grid-cols-2 gap-2 sm:flex">
          <Select
            v-model="category"
            :options="categoryOptions"
            aria-label="Filter by category"
            class="min-w-0 sm:w-44"
          />
          <Select
            v-model="year"
            :options="yearOptions"
            aria-label="Filter by academic year"
            class="min-w-0 sm:w-36"
          />
        </div>
      </div>

      <div class="mt-3 flex flex-wrap items-center gap-2">
        <Button variant="outline" size="sm" @click="showArchived = !showArchived">
          <component :is="showArchived ? RotateCcw : Archive" class="h-3.5 w-3.5" />
          {{ showArchived ? 'Back to active documents' : `Archived (${archivedCount})` }}
        </Button>
        <span v-if="showArchived" class="text-[12px] text-muted-foreground">
          Archived documents are hidden from the active repository.
        </span>
      </div>

      <Card v-if="filteredDocuments.length" class="mt-4 overflow-hidden" data-testid="document-table">
        <Table>
          <TableHeader>
            <TableRow class="hover:bg-transparent">
              <TableHead class="pl-5">Document</TableHead>
              <TableHead class="hidden sm:table-cell">Category</TableHead>
              <TableHead class="hidden lg:table-cell">Academic year</TableHead>
              <TableHead class="hidden text-right sm:table-cell">Version</TableHead>
              <TableHead class="hidden xl:table-cell">Updated</TableHead>
              <TableHead class="w-32 pr-5 text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="document in filteredDocuments" :key="document.id">
              <TableCell class="pl-5">
                <button type="button" class="max-w-[420px] text-left" @click="openDocument(document)">
                  <span class="block truncate text-sm font-medium">{{ document.title }}</span>
                  <span class="mt-0.5 block truncate text-[13px] text-muted-foreground">
                    {{ fileType(document.latest_version?.file_name) }} · {{ formatBytes(document.latest_version?.file_size_bytes) }} · v{{ document.current_version }}
                    <span class="sm:hidden"> · {{ document.category?.name ?? 'Uncategorised' }} · {{ formatDate(document.updated_at) }}</span>
                  </span>
                </button>
              </TableCell>
              <TableCell class="hidden sm:table-cell">
                <Badge variant="outline">{{ document.category?.name ?? 'Uncategorised' }}</Badge>
              </TableCell>
              <TableCell class="hidden text-[13px] text-muted-foreground lg:table-cell">
                {{ document.academic_year }}
              </TableCell>
              <TableCell class="tabular-nums hidden text-right text-[13px] text-muted-foreground sm:table-cell">
                v{{ document.current_version }}
              </TableCell>
              <TableCell class="hidden text-[13px] text-muted-foreground xl:table-cell">
                {{ formatDate(document.updated_at) }}
              </TableCell>
              <TableCell class="pr-5 text-right">
                <div class="relative inline-block text-left" @click.stop>
                  <Button
                    variant="ghost"
                    size="xs"
                    :disabled="actionBusyId === document.id"
                    :aria-label="`Actions for ${document.title}`"
                    :aria-expanded="openMenuId === document.id"
                    @click="toggleMenu(document.id)"
                  >
                    Actions
                    <MoreHorizontal class="h-3.5 w-3.5" />
                  </Button>
                  <div
                    v-if="openMenuId === document.id"
                    class="absolute right-0 top-full z-30 mt-1 w-48 rounded-md border bg-card p-1 shadow-lg"
                    role="menu"
                  >
                    <button type="button" class="flex w-full items-center gap-2 rounded px-2.5 py-2 text-left text-[13px] transition-colors hover:bg-secondary" role="menuitem" @click="openDocument(document)">
                      <FileText class="h-3.5 w-3.5" />
                      Open
                    </button>
                    <button type="button" class="flex w-full items-center gap-2 rounded px-2.5 py-2 text-left text-[13px] transition-colors hover:bg-secondary" role="menuitem" @click="openRename(document)">
                      <Pencil class="h-3.5 w-3.5" />
                      Rename
                    </button>
                    <button type="button" class="flex w-full items-center gap-2 rounded px-2.5 py-2 text-left text-[13px] transition-colors hover:bg-secondary" role="menuitem" @click="downloadDocument(document)">
                      <Download class="h-3.5 w-3.5" />
                      Download
                    </button>
                    <button v-if="!document.is_archived" type="button" class="flex w-full items-center gap-2 rounded px-2.5 py-2 text-left text-[13px] transition-colors hover:bg-secondary" role="menuitem" @click="openVersion(document)">
                      <Upload class="h-3.5 w-3.5" />
                      New version
                    </button>
                    <button type="button" class="flex w-full items-center gap-2 rounded px-2.5 py-2 text-left text-[13px] transition-colors hover:bg-secondary" role="menuitem" @click="toggleArchive(document)">
                      <component :is="document.is_archived ? RotateCcw : Archive" class="h-3.5 w-3.5" />
                      {{ document.is_archived ? 'Restore' : 'Archive' }}
                    </button>
                    <button type="button" class="flex w-full items-center gap-2 rounded px-2.5 py-2 text-left text-[13px] text-negative transition-colors hover:bg-negative-soft" role="menuitem" @click="openDelete(document)">
                      <Trash2 class="h-3.5 w-3.5" />
                      Delete
                    </button>
                  </div>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
        <div class="flex items-center justify-between border-t px-5 py-3 text-[13px] text-muted-foreground">
          <span>Showing {{ filteredDocuments.length }} of {{ plural(documents.length, 'document') }}</span>
          <span>Versions are kept for every file</span>
        </div>
      </Card>

      <Card v-else class="mt-4 p-5">
        <EmptyState
          :title="documents.length
            ? 'No documents match those filters'
            : showArchived ? 'No archived documents' : 'No documents yet'"
          :description="documents.length
            ? 'Clear the search or choose a different category and academic year.'
            : showArchived ? 'Archive a document to see it here.' : 'Upload the first document to build the department repository.'"
        >
          <Button v-if="!documents.length && !showArchived" size="sm" class="mt-3" @click="uploadOpen = true">
            <Upload class="h-4 w-4" />
            Upload document
          </Button>
        </EmptyState>
      </Card>

      <div class="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-12">
        <Card class="flex flex-col lg:col-span-7">
          <CardHeader class="pb-3">
            <CardTitle>Repository summary</CardTitle>
            <CardDescription class="mt-1">Files by category.</CardDescription>
          </CardHeader>
          <div class="flex flex-1 flex-col border-t px-5 py-4">
            <div class="flex items-baseline justify-between gap-3">
              <span class="text-[13px] text-muted-foreground">Total documents</span>
              <span class="text-2xl font-medium leading-none tracking-[-0.02em] tabular-nums">{{ documents.length }}</span>
            </div>
            <div v-if="categoryRows.length" class="mt-4 space-y-2.5">
              <div v-for="item in categoryRows" :key="item.key" class="flex items-center gap-3">
                <span class="w-28 shrink-0 text-[13px] text-muted-foreground">{{ item.label }}</span>
                <div class="h-1.5 flex-1 overflow-hidden rounded-full bg-secondary">
                  <div
                    class="h-full rounded-full bg-brand"
                    :style="{ width: documents.length ? `${(item.count / documents.length) * 100}%` : '0%' }"
                  />
                </div>
                <span class="w-4 text-right text-[13px] tabular-nums">{{ item.count }}</span>
              </div>
            </div>
          </div>
        </Card>

        <Card class="flex flex-col lg:col-span-5">
          <CardHeader class="pb-3">
            <CardTitle>Storage</CardTitle>
            <CardDescription class="mt-1">Real file sizes from stored versions.</CardDescription>
          </CardHeader>
          <dl class="flex flex-1 flex-col justify-between gap-2 border-t px-5 py-4">
            <div class="flex items-center justify-between gap-3 text-[13px]">
              <dt class="text-muted-foreground">Storage used</dt>
              <dd class="tabular-nums">{{ formatBytes(storageUsed) }}</dd>
            </div>
            <div class="flex items-center justify-between gap-3 text-[13px]">
              <dt class="text-muted-foreground">Largest file</dt>
              <dd class="tabular-nums">{{ formatBytes(largestFile) }}</dd>
            </div>
            <div class="flex items-center justify-between gap-3 text-[13px]">
              <dt class="text-muted-foreground">Oldest record</dt>
              <dd>{{ oldestRecord }}</dd>
            </div>
            <div class="flex items-center justify-between gap-3 text-[13px]">
              <dt class="text-muted-foreground">Last update</dt>
              <dd>{{ lastUpdate }}</dd>
            </div>
            <div class="flex items-center justify-between gap-3 text-[13px]">
              <dt class="text-muted-foreground">Checksums</dt>
              <dd>Verified on upload</dd>
            </div>
          </dl>
        </Card>
      </div>
    </template>

    <Dialog :open="selected !== null" @update:open="value => { if (!value) selected = null }">
      <DialogContent class="max-w-2xl" data-testid="document-detail">
        <DialogHeader v-if="selected" class="border-b pb-4">
          <div class="flex flex-wrap items-center gap-2">
            <Badge variant="outline">{{ selected.category?.name ?? 'Uncategorised' }}</Badge>
            <span class="text-[13px] text-muted-foreground">
              {{ selected.academic_year }} · v{{ selected.current_version }}
            </span>
          </div>
          <DialogTitle class="break-words pr-8 leading-snug">{{ selected.title }}</DialogTitle>
          <DialogDescription class="break-words">
            {{ selected.latest_version?.file_name ?? 'No file' }} · {{ formatBytes(selected.latest_version?.file_size_bytes) }} · uploaded {{ formatDate(selected.created_at) }}
          </DialogDescription>
        </DialogHeader>

        <div v-if="selected" class="min-w-0 space-y-5">
          <div class="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" @click="downloadDocument(selected)">
              <Download class="h-3.5 w-3.5" />
              Download
            </Button>
            <Button v-if="!selected.is_archived" variant="outline" size="sm" @click="openVersion(selected)">
              <Upload class="h-3.5 w-3.5" />
              New version
            </Button>
            <Button variant="ghost" size="sm" @click="toggleArchive(selected)">
              <component :is="selected.is_archived ? RotateCcw : Archive" class="h-3.5 w-3.5" />
              {{ selected.is_archived ? 'Restore' : 'Archive' }}
            </Button>
            <Button variant="ghost" size="sm" class="text-negative" @click="openDelete(selected)">
              <Trash2 class="h-3.5 w-3.5" />
              Delete
            </Button>
          </div>

          <div v-if="selected.drive_file_id" class="flex flex-col gap-3 rounded-md border border-brand/20 bg-brand-soft px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div class="min-w-0">
              <p class="text-[13px] font-medium text-brand">Archived from a meeting</p>
              <p class="mt-0.5 text-[13px] text-brand/80">The published minutes are stored with their source meeting.</p>
            </div>
            <Button variant="outline" size="sm" as-child class="shrink-0 self-start sm:self-auto">
              <NuxtLink :to="`/meetings/${selected.drive_file_id}/review`">Open meeting</NuxtLink>
            </Button>
          </div>

          <div class="rounded-md border bg-muted/40 p-4">
            <div class="flex flex-wrap items-center gap-2">
              <p class="text-[13px] font-medium text-muted-foreground">Summary</p>
              <div
                class="inline-flex rounded-md border bg-card/60 p-0.5"
                role="group"
                aria-label="Summary language"
              >
                <button
                  type="button"
                  class="rounded px-2.5 py-1 text-[12px] font-medium transition-colors"
                  :class="summaryLanguage === 'en' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'"
                  :aria-pressed="summaryLanguage === 'en'"
                  @click="summaryLanguage = 'en'"
                >
                  English
                </button>
                <button
                  type="button"
                  class="rounded px-2.5 py-1 font-khmer text-[12px] font-medium transition-colors"
                  :class="summaryLanguage === 'km' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'"
                  :aria-pressed="summaryLanguage === 'km'"
                  @click="summaryLanguage = 'km'"
                >
                  ខ្មែរ
                </button>
              </div>
              <Button
                v-if="selectedSummary"
                variant="ghost"
                size="sm"
                class="ml-auto text-brand"
                :disabled="summarizing"
                @click="summarizeSelected"
              >
                <span v-if="summarizing" class="h-3 w-3 animate-spin rounded-full border-2 border-brand border-t-transparent" />
                {{ summarizing ? 'Regenerating…' : `Regenerate in ${summaryLanguage === 'km' ? 'Khmer' : 'English'}` }}
              </Button>
            </div>

            <p
              v-if="selectedSummary"
              data-testid="document-summary"
              class="mt-2 break-words text-sm leading-relaxed"
              :class="summaryDraftLanguage === 'km' ? 'font-khmer' : ''"
            >
              {{ selectedSummary }}
            </p>
            <div v-else class="mt-2 flex flex-col items-start gap-2">
              <p class="text-[13px] text-muted-foreground">No AI summary has been generated for this document.</p>
              <Button variant="outline" size="sm" :disabled="summarizing" @click="summarizeSelected">
                {{ summarizing ? 'Generating…' : `Generate summary in ${summaryLanguage === 'km' ? 'Khmer' : 'English'}` }}
              </Button>
            </div>

            <p
              v-if="selectedSummary && summaryDraftLanguage && summaryDraftLanguage !== summaryLanguage"
              class="mt-2 text-[12px] text-muted-foreground"
            >
              Current summary is in {{ summaryDraftLanguage === 'km' ? 'Khmer' : 'English' }}. Regenerate to apply {{ summaryLanguage === 'km' ? 'Khmer' : 'English' }}.
            </p>
          </div>

          <div v-if="selectedEntities.length">
            <p class="text-[13px] font-medium text-muted-foreground">Extracted details</p>
            <dl class="mt-2 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div v-for="entity in selectedEntities" :key="entity.label" class="min-w-0">
                <dt class="text-[13px] capitalize text-muted-foreground">{{ entity.label }}</dt>
                <dd class="mt-1.5 flex flex-wrap gap-1.5">
                  <Badge
                    v-for="(entry, index) in entity.values"
                    :key="`${entity.label}-${index}`"
                    variant="secondary"
                    class="max-w-full whitespace-normal break-words text-left"
                  >
                    {{ entry }}
                  </Badge>
                </dd>
              </div>
            </dl>
          </div>

          <div v-if="selectedVersions.length">
            <p class="text-[13px] font-medium text-muted-foreground">Version history</p>
            <div class="mt-2 divide-y rounded-md border">
              <div
                v-for="version in selectedVersions"
                :key="version.id"
                class="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-3 py-2.5 text-[13px]"
              >
                <span class="font-medium">v{{ version.version_number }}</span>
                <span class="min-w-0 flex-1 truncate text-muted-foreground">{{ version.file_name }}</span>
                <span class="tabular-nums shrink-0 text-muted-foreground">{{ formatDate(version.created_at) }}</span>
                <Button variant="ghost" size="xs" :disabled="actionBusyId === selected?.id" @click="selected && downloadDocument(selected, version.id)">
                  <Download class="h-3.5 w-3.5" />
                  Download
                </Button>
              </div>
            </div>
          </div>
        </div>

        <DialogFooter class="border-t pt-4">
          <Button variant="outline" @click="selected = null">Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog :open="uploadOpen" @update:open="value => { uploadOpen = value; if (!value) resetUpload() }">
      <DialogContent class="max-w-lg" data-testid="upload-document">
        <DialogHeader>
          <DialogTitle>Add a document</DialogTitle>
          <DialogDescription>
            Upload a file or import a Google Docs, Sheets, Slides, or Drive link. An optional AI summary can be generated later from the document panel.
          </DialogDescription>
        </DialogHeader>

        <div class="grid grid-cols-2 gap-1 rounded-md border bg-muted/30 p-1" role="tablist" aria-label="Document source">
          <button
            type="button"
            role="tab"
            :aria-selected="uploadMode === 'file'"
            class="flex h-8 items-center justify-center gap-2 rounded text-[13px] font-medium transition-colors"
            :class="uploadMode === 'file' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'"
            @click="uploadMode = 'file'"
          >
            <Upload class="h-3.5 w-3.5" />
            Upload file
          </button>
          <button
            type="button"
            role="tab"
            :aria-selected="uploadMode === 'google'"
            class="flex h-8 items-center justify-center gap-2 rounded text-[13px] font-medium transition-colors"
            :class="uploadMode === 'google' ? 'bg-card text-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground'"
            @click="uploadMode = 'google'"
          >
            <Link2 class="h-3.5 w-3.5" />
            Google Drive link
          </button>
        </div>

        <div class="space-y-4">
          <div v-if="uploadMode === 'file'" class="space-y-1.5">
            <Label for="document-file">File</Label>
            <input id="document-file" type="file" class="sr-only" @change="onFile" />
            <label
              for="document-file"
              class="flex min-h-[88px] cursor-pointer flex-col items-center justify-center gap-1 rounded-md border border-dashed border-input bg-muted/30 px-4 py-4 text-center transition-colors hover:bg-muted/60"
            >
              <Upload class="h-4 w-4 text-muted-foreground" />
              <span class="text-[13px] font-medium">
                {{ uploadForm.file?.name ?? 'Choose a PDF, DOCX, XLSX or CSV' }}
              </span>
              <span class="text-[13px] text-muted-foreground">Up to 50 MB</span>
            </label>
          </div>

          <div v-else class="space-y-1.5">
            <Label for="google-drive-url">Google Docs, Sheets, Slides or Drive link</Label>
            <Input
              id="google-drive-url"
              v-model="uploadForm.googleUrl"
              placeholder="https://docs.google.com/document/d/..."
            />
            <div class="flex flex-wrap items-center gap-2">
              <Button type="button" variant="outline" size="sm" @click="openGoogleDrive">
                <ExternalLink class="h-3.5 w-3.5" />
                Open Google Drive to search
              </Button>
              <span class="text-[12px] text-muted-foreground">Choose a file, copy its link, then paste it above.</span>
            </div>
            <p class="text-[12px] leading-relaxed text-muted-foreground">
              The file must be viewable by anyone with the link. Google Docs become DOCX, Sheets become XLSX, and Slides become PDF.
            </p>
          </div>

          <div class="space-y-1.5">
            <Label for="document-title">
              Title
              <span class="font-normal text-muted-foreground">(optional)</span>
            </Label>
            <Input id="document-title" v-model="uploadForm.title" placeholder="Document title" />
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-1.5">
              <Label for="document-category">Category</Label>
              <Select
                id="document-category"
                v-model="uploadForm.category_id"
                :options="uploadCategoryOptions"
                aria-label="Category"
              />
            </div>
            <div class="space-y-1.5">
              <Label for="document-year">Academic year</Label>
              <Input id="document-year" v-model="uploadForm.year" placeholder="2026–2027" />
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" :disabled="uploading" @click="uploadOpen = false; resetUpload()">Cancel</Button>
          <Button :disabled="uploading" @click="addDocument">
            {{ uploading
              ? (uploadMode === 'google' ? 'Importing…' : 'Uploading…')
              : (uploadMode === 'google' ? 'Import from Google' : 'Add document') }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="renameOpen">
      <DialogContent class="max-w-md">
        <DialogHeader>
          <DialogTitle>Rename document</DialogTitle>
          <DialogDescription>This title appears in the repository, search results, and exports.</DialogDescription>
        </DialogHeader>
        <div class="space-y-1.5">
          <Label for="rename-document-title">Title</Label>
          <Input id="rename-document-title" v-model="renameTitle" @keyup.enter="renameDocument" />
        </div>
        <DialogFooter>
          <Button variant="outline" :disabled="renaming" @click="renameOpen = false">Cancel</Button>
          <Button :disabled="renaming || !renameTitle.trim()" @click="renameDocument">
            {{ renaming ? 'Saving…' : 'Save name' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="deleteOpen">
      <DialogContent class="max-w-md">
        <DialogHeader>
          <DialogTitle>Delete this document?</DialogTitle>
          <DialogDescription>
            This permanently removes the document and all of its stored versions. This cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <div class="rounded-md border border-negative/20 bg-negative-soft px-3 py-2.5 text-[13px] text-negative">
          {{ deleteTarget?.title }}
        </div>
        <DialogFooter>
          <Button variant="outline" :disabled="deleting" @click="deleteOpen = false">Cancel</Button>
          <Button variant="destructive" :disabled="deleting" @click="deleteDocument">
            {{ deleting ? 'Deleting…' : 'Delete document' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="versionOpen">
      <DialogContent class="max-w-md">
        <DialogHeader>
          <DialogTitle>Upload a new version</DialogTitle>
          <DialogDescription>
            {{ versionTarget?.title }} · currently v{{ versionTarget?.current_version }}. Previous versions remain downloadable.
          </DialogDescription>
        </DialogHeader>
        <div class="space-y-1.5">
          <Label for="document-version-file">File</Label>
          <input id="document-version-file" type="file" class="sr-only" @change="onVersionFile" />
          <label
            for="document-version-file"
            class="flex min-h-[88px] cursor-pointer flex-col items-center justify-center gap-1 rounded-md border border-dashed border-input bg-muted/30 px-4 py-4 text-center transition-colors hover:bg-muted/60"
          >
            <Upload class="h-4 w-4 text-muted-foreground" />
            <span class="text-[13px] font-medium">
              {{ versionFile?.name ?? 'Choose the new file' }}
            </span>
            <span class="text-[13px] text-muted-foreground">PDF, DOCX, XLSX or CSV · up to 50 MB</span>
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" :disabled="versionUploading" @click="versionOpen = false">Cancel</Button>
          <Button :disabled="versionUploading || !versionFile" @click="uploadVersion">
            {{ versionUploading ? 'Uploading…' : 'Upload version' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
