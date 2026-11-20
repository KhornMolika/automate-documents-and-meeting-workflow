<script setup lang="ts">
import { computed, ref } from 'vue'
import { Search, Upload } from 'lucide-vue-next'
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
  api<WorkspaceDocument[]>('/documents', { query: { limit: 200 } }),
)

const categories = computed(() => categoryData.value ?? [])
const documents = computed(() => documentData.value ?? [])
const departmentName = computed(() => user.value?.department?.name ?? 'Department workspace')

const search = ref('')
const category = ref('ALL')
const year = ref('ALL')
const selected = ref<WorkspaceDocument | null>(null)
const uploadOpen = ref(false)
const uploading = ref(false)
const summarizing = ref(false)
const uploadForm = ref({
  title: '',
  category_id: '',
  year: '2026–2027',
  file: null as File | null,
})

const years = computed(() => [...new Set(documents.value.map(document => document.academic_year))].sort().reverse())

const filteredDocuments = computed(() => {
  const query = search.value.trim().toLowerCase()
  return documents.value.filter(document => {
    const matchesCategory = category.value === 'ALL' || document.category?.id === category.value
    const matchesYear = year.value === 'ALL' || document.academic_year === year.value
    const matchesQuery =
      !query ||
      [document.title, document.category?.name, document.latest_version?.abstract_summary, document.latest_version?.file_name]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
        .includes(query)
    return matchesCategory && matchesYear && matchesQuery
  })
})

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

const selectedEntities = computed(() => parseEntities(selected.value?.latest_version?.extracted_entities))
const selectedVersions = computed(() => selected.value?.versions ?? [])

function openDocument(document: WorkspaceDocument) {
  selected.value = document
}

function onFile(event: Event) {
  const input = event.target as HTMLInputElement
  uploadForm.value.file = input.files?.[0] ?? null
}

function resetUpload() {
  uploadForm.value = {
    title: '',
    category_id: '',
    year: '2026–2027',
    file: null,
  }
}

async function addDocument() {
  if (!uploadForm.value.file) {
    toast.error('Choose a file first.')
    return
  }
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', uploadForm.value.file)
    if (uploadForm.value.title.trim()) formData.append('title', uploadForm.value.title.trim())
    if (uploadForm.value.category_id) formData.append('category_id', uploadForm.value.category_id)
    formData.append('academic_year', uploadForm.value.year)

    const created = await api<WorkspaceDocument>('/documents/upload', {
      method: 'POST',
      body: formData,
    })
    await refresh()
    uploadOpen.value = false
    resetUpload()
    toast.success(
      created.latest_version?.abstract_summary
        ? 'Document uploaded and summarized.'
        : 'Document uploaded. Use Generate summary in the document panel to create an AI abstract.',
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
    const updated = await api<WorkspaceDocument>(`/documents/${selected.value.id}/summarize`, {
      method: 'POST',
    })
    selected.value = updated
    await refresh()
    toast.success('Document summary generated.')
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Summary generation failed.')
  } finally {
    summarizing.value = false
  }
}
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

    <LoadingState v-if="pending" class="mt-6" />
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
        <div class="flex gap-2">
          <select
            v-model="category"
            aria-label="Filter by category"
            class="h-9 flex-1 rounded-md border border-input bg-card px-3 text-sm text-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30 max-sm:h-10 sm:flex-none"
          >
            <option value="ALL">All categories</option>
            <option v-for="item in categories" :key="item.id" :value="item.id">{{ item.name }}</option>
          </select>
          <select
            v-model="year"
            aria-label="Filter by academic year"
            class="h-9 flex-1 rounded-md border border-input bg-card px-3 text-sm text-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30 max-sm:h-10 sm:flex-none"
          >
            <option value="ALL">All years</option>
            <option v-for="item in years" :key="item" :value="item">{{ item }}</option>
          </select>
        </div>
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
              <TableHead class="w-16 pr-5 text-right">Open</TableHead>
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
                <Button variant="ghost" size="xs" @click="openDocument(document)">Open</Button>
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
          :title="documents.length ? 'No documents match those filters' : 'No documents yet'"
          :description="documents.length ? 'Clear the search or choose a different category and academic year.' : 'Upload the first document to build the department repository.'"
        >
          <Button v-if="!documents.length" size="sm" class="mt-3" @click="uploadOpen = true">
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
        <DialogHeader v-if="selected">
          <div class="flex flex-wrap items-center gap-2">
            <Badge variant="outline">{{ selected.category?.name ?? 'Uncategorised' }}</Badge>
            <span class="text-[13px] text-muted-foreground">
              {{ selected.academic_year }} · v{{ selected.current_version }}
            </span>
          </div>
          <DialogTitle class="pr-8">{{ selected.title }}</DialogTitle>
          <DialogDescription>
            {{ selected.latest_version?.file_name ?? 'No file' }} · {{ formatBytes(selected.latest_version?.file_size_bytes) }} · uploaded {{ formatDate(selected.created_at) }}
          </DialogDescription>
        </DialogHeader>

        <div v-if="selected" class="space-y-5">
          <div class="rounded-md border bg-muted/40 p-4">
            <p class="text-[13px] font-medium text-muted-foreground">AI abstract</p>
            <p v-if="selected.latest_version?.abstract_summary" class="mt-1.5 text-sm leading-relaxed">
              {{ selected.latest_version.abstract_summary }}
            </p>
            <div v-else class="mt-2 flex flex-col items-start gap-2">
              <p class="text-[13px] text-muted-foreground">No AI summary has been generated for this document.</p>
              <Button variant="outline" size="sm" :disabled="summarizing" @click="summarizeSelected">
                {{ summarizing ? 'Generating…' : 'Generate summary' }}
              </Button>
            </div>
          </div>

          <div v-if="selectedEntities.length">
            <p class="text-[13px] font-medium text-muted-foreground">Extracted details</p>
            <dl class="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div v-for="entity in selectedEntities" :key="entity.label">
                <dt class="text-[13px] capitalize text-muted-foreground">{{ entity.label }}</dt>
                <dd class="mt-0.5 text-[13px] font-medium">{{ entity.value }}</dd>
              </div>
            </dl>
          </div>

          <div v-if="selectedVersions.length">
            <p class="text-[13px] font-medium text-muted-foreground">Version history</p>
            <div class="mt-2 divide-y rounded-md border">
              <div
                v-for="version in selectedVersions"
                :key="version.id"
                class="flex items-center justify-between gap-3 px-3 py-2.5 text-[13px]"
              >
                <span class="font-medium">v{{ version.version_number }}</span>
                <span class="text-muted-foreground">{{ version.file_name }}</span>
                <span class="tabular-nums text-muted-foreground">{{ formatDate(version.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" @click="selected = null">Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="uploadOpen">
      <DialogContent class="max-w-lg" data-testid="upload-document">
        <DialogHeader>
          <DialogTitle>Add a document</DialogTitle>
          <DialogDescription>
            The file is parsed, checksummed and stored by the API. AI summarization runs through the configured LLM provider.
          </DialogDescription>
        </DialogHeader>

        <div class="space-y-4">
          <div class="space-y-1.5">
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

          <div class="space-y-1.5">
            <Label for="document-title">Title</Label>
            <Input id="document-title" v-model="uploadForm.title" placeholder="Document title" />
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div class="space-y-1.5">
              <Label for="document-category">Category</Label>
              <select
                id="document-category"
                v-model="uploadForm.category_id"
                class="h-9 w-full rounded-md border border-input bg-card px-3 text-sm focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30 max-sm:h-10"
              >
                <option value="">Uncategorised</option>
                <option v-for="item in categories" :key="item.id" :value="item.id">{{ item.name }}</option>
              </select>
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
            {{ uploading ? 'Uploading…' : 'Add document' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
