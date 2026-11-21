<script setup lang="ts">
import { computed, ref } from 'vue'
import { KeyRound, Plus, ShieldCheck, UserCog } from 'lucide-vue-next'
import { toast } from 'vue-sonner'
import { Badge } from '~/components/ui/badge'
import { Button } from '~/components/ui/button'
import { Card } from '~/components/ui/card'
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
import ErrorState from '~/components/workspace/ErrorState.vue'
import LoadingState from '~/components/workspace/LoadingState.vue'
import PageHeader from '~/components/workspace/PageHeader.vue'
import { useApi } from '~/composables/useApi'

useHead({ title: 'Administration · ACLEDA University' })

type AdminRole = { id: string, role_name: string, description?: string | null }
type AdminDepartment = { id: string, department_code: string, name: string, faculty: string }
type AdminUser = {
  id: string
  email: string
  full_name: string
  student_or_staff_id?: string | null
  department_id?: string | null
  is_active: boolean
  roles: AdminRole[]
  department?: AdminDepartment | null
  created_at: string
}

const api = useApi()
const {
  data,
  pending,
  error,
  refresh,
} = await useAsyncData('admin-console', async () => {
  const [users, roles, departments] = await Promise.all([
    api<AdminUser[]>('/auth/users'),
    api<AdminRole[]>('/auth/roles'),
    api<AdminDepartment[]>('/auth/departments'),
  ])
  return { users, roles, departments }
})

const users = computed(() => data.value?.users ?? [])
const roles = computed(() => data.value?.roles ?? [])
const departments = computed(() => data.value?.departments ?? [])
const departmentOptions = computed(() => [
  { value: 'NONE', label: 'No department' },
  ...departments.value.map(department => ({ value: department.id, label: department.name })),
])
const roleOptions = computed(() =>
  roles.value.map(role => ({ value: role.role_name, label: role.role_name })),
)

const createOpen = ref(false)
const createSaving = ref(false)
const createForm = ref({
  email: '',
  full_name: '',
  password: '',
  student_or_staff_id: '',
  department_id: 'NONE',
  role: 'Staff',
})

const editOpen = ref(false)
const editSaving = ref(false)
const editUser = ref<AdminUser | null>(null)
const editForm = ref({
  full_name: '',
  department_id: 'NONE',
  role: 'Staff',
  is_active: true,
})

const passwordOpen = ref(false)
const passwordSaving = ref(false)
const passwordUser = ref<AdminUser | null>(null)
const passwordValue = ref('')

const departmentOpen = ref(false)
const departmentSaving = ref(false)
const departmentForm = ref({ department_code: '', name: '', faculty: '' })

function roleName(user: AdminUser) {
  return user.roles.map(role => role.role_name).join(', ') || 'Staff'
}

function resetCreateForm() {
  createForm.value = {
    email: '',
    full_name: '',
    password: '',
    student_or_staff_id: '',
    department_id: 'NONE',
    role: 'Staff',
  }
}

async function createUser() {
  createSaving.value = true
  try {
    await api('/auth/register', {
      method: 'POST',
      body: {
        email: createForm.value.email.trim(),
        full_name: createForm.value.full_name.trim(),
        password: createForm.value.password,
        student_or_staff_id: createForm.value.student_or_staff_id.trim() || null,
        department_id: createForm.value.department_id === 'NONE' ? null : createForm.value.department_id,
        roles: [createForm.value.role],
      },
    })
    createOpen.value = false
    resetCreateForm()
    await refresh()
    toast.success('User created.')
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not create the user.')
  } finally {
    createSaving.value = false
  }
}

function openEdit(user: AdminUser) {
  editUser.value = user
  editForm.value = {
    full_name: user.full_name,
    department_id: user.department_id ?? 'NONE',
    role: user.roles[0]?.role_name ?? 'Staff',
    is_active: user.is_active,
  }
  editOpen.value = true
}

async function saveUser() {
  if (!editUser.value) return
  editSaving.value = true
  try {
    await api(`/auth/users/${editUser.value.id}`, {
      method: 'PATCH',
      body: {
        full_name: editForm.value.full_name.trim(),
        department_id: editForm.value.department_id === 'NONE' ? null : editForm.value.department_id,
        roles: [editForm.value.role],
        is_active: editForm.value.is_active,
      },
    })
    editOpen.value = false
    await refresh()
    toast.success('User updated.')
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not update the user.')
  } finally {
    editSaving.value = false
  }
}

function openPassword(user: AdminUser) {
  passwordUser.value = user
  passwordValue.value = ''
  passwordOpen.value = true
}

async function resetPassword() {
  if (!passwordUser.value) return
  passwordSaving.value = true
  try {
    await api(`/auth/users/${passwordUser.value.id}/password`, {
      method: 'POST',
      body: { password: passwordValue.value },
    })
    passwordOpen.value = false
    toast.success('Password reset.')
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not reset the password.')
  } finally {
    passwordSaving.value = false
  }
}

async function createDepartment() {
  departmentSaving.value = true
  try {
    await api('/auth/departments', {
      method: 'POST',
      body: {
        department_code: departmentForm.value.department_code.trim(),
        name: departmentForm.value.name.trim(),
        faculty: departmentForm.value.faculty.trim(),
      },
    })
    departmentOpen.value = false
    departmentForm.value = { department_code: '', name: '', faculty: '' }
    await refresh()
    toast.success('Department created.')
  } catch (err: any) {
    toast.error(err?.data?.detail ?? 'Could not create the department.')
  } finally {
    departmentSaving.value = false
  }
}
</script>

<template>
  <div>
    <PageHeader title="Administration" description="Manage users, departments, roles and access.">
      <template #actions>
        <Button variant="outline" @click="departmentOpen = true">
          <Plus class="h-4 w-4" />
          New department
        </Button>
        <Button @click="createOpen = true">
          <UserCog class="h-4 w-4" />
          New user
        </Button>
      </template>
    </PageHeader>

    <LoadingState v-if="pending" class="mt-6" />
    <ErrorState v-else-if="error" class="mt-6" :message="error.message" @retry="refresh" />

    <template v-else>
      <Card class="mt-6 overflow-hidden">
        <div class="flex items-center justify-between border-b px-5 py-3">
          <div>
            <p class="text-sm font-medium">Users</p>
            <p class="text-[13px] text-muted-foreground">{{ users.length }} accounts in this workspace.</p>
          </div>
          <Badge variant="outline"><ShieldCheck class="mr-1 h-3 w-3" /> Administrator view</Badge>
        </div>
        <Table>
          <TableHeader>
            <TableRow class="hover:bg-transparent">
              <TableHead class="pl-5">User</TableHead>
              <TableHead class="hidden sm:table-cell">Department</TableHead>
              <TableHead class="hidden lg:table-cell">Role</TableHead>
              <TableHead>Status</TableHead>
              <TableHead class="w-40 pr-5 text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow v-for="user in users" :key="user.id">
              <TableCell class="pl-5">
                <p class="text-sm font-medium">{{ user.full_name }}</p>
                <p class="text-[13px] text-muted-foreground">{{ user.email }}</p>
              </TableCell>
              <TableCell class="hidden text-[13px] text-muted-foreground sm:table-cell">
                {{ user.department?.name ?? 'No department' }}
              </TableCell>
              <TableCell class="hidden lg:table-cell">
                <Badge variant="outline">{{ roleName(user) }}</Badge>
              </TableCell>
              <TableCell>
                <Badge :variant="user.is_active ? 'secondary' : 'negative'">
                  {{ user.is_active ? 'Active' : 'Disabled' }}
                </Badge>
              </TableCell>
              <TableCell class="pr-5 text-right">
                <Button variant="ghost" size="xs" @click="openEdit(user)">Edit</Button>
                <Button variant="ghost" size="xs" @click="openPassword(user)">
                  <KeyRound class="h-3.5 w-3.5" />
                  Password
                </Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </Card>

      <Card class="mt-4 p-5">
        <div class="flex items-center justify-between gap-3">
          <div>
            <p class="text-sm font-medium">Departments</p>
            <p class="text-[13px] text-muted-foreground">Departments scope documents, meetings and follow-ups.</p>
          </div>
          <Badge variant="outline">{{ departments.length }}</Badge>
        </div>
        <div class="mt-3 divide-y rounded-md border">
          <div v-for="department in departments" :key="department.id" class="flex flex-wrap items-center gap-2 px-3 py-2.5 text-[13px]">
            <span class="font-medium">{{ department.name }}</span>
            <Badge variant="secondary">{{ department.department_code }}</Badge>
            <span class="text-muted-foreground">{{ department.faculty }}</span>
          </div>
        </div>
      </Card>
    </template>

    <Dialog v-model:open="createOpen">
      <DialogContent class="max-w-lg">
        <DialogHeader>
          <DialogTitle>New user</DialogTitle>
          <DialogDescription>Create an account and assign its department and role.</DialogDescription>
        </DialogHeader>
        <div class="space-y-3">
          <div class="space-y-1.5">
            <Label for="admin-user-name">Full name</Label>
            <Input id="admin-user-name" v-model="createForm.full_name" />
          </div>
          <div class="space-y-1.5">
            <Label for="admin-user-email">Email</Label>
            <Input id="admin-user-email" v-model="createForm.email" type="email" />
          </div>
          <div class="space-y-1.5">
            <Label for="admin-user-password">Temporary password</Label>
            <Input id="admin-user-password" v-model="createForm.password" type="password" />
          </div>
          <div class="grid gap-3 sm:grid-cols-2">
            <div class="space-y-1.5">
              <Label for="admin-user-department">Department</Label>
              <Select id="admin-user-department" v-model="createForm.department_id" :options="departmentOptions" aria-label="Department" />
            </div>
            <div class="space-y-1.5">
              <Label for="admin-user-role">Role</Label>
              <Select id="admin-user-role" v-model="createForm.role" :options="roleOptions" aria-label="Role" />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" :disabled="createSaving" @click="createOpen = false">Cancel</Button>
          <Button :disabled="createSaving || !createForm.email || !createForm.full_name || createForm.password.length < 8" @click="createUser">
            {{ createSaving ? 'Creating…' : 'Create user' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="editOpen">
      <DialogContent class="max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit user</DialogTitle>
          <DialogDescription>{{ editUser?.email }}</DialogDescription>
        </DialogHeader>
        <div class="space-y-3">
          <div class="space-y-1.5">
            <Label for="admin-edit-name">Full name</Label>
            <Input id="admin-edit-name" v-model="editForm.full_name" />
          </div>
          <div class="grid gap-3 sm:grid-cols-2">
            <div class="space-y-1.5">
              <Label for="admin-edit-department">Department</Label>
              <Select id="admin-edit-department" v-model="editForm.department_id" :options="departmentOptions" aria-label="Department" />
            </div>
            <div class="space-y-1.5">
              <Label for="admin-edit-role">Role</Label>
              <Select id="admin-edit-role" v-model="editForm.role" :options="roleOptions" aria-label="Role" />
            </div>
          </div>
          <label class="flex items-center gap-2 text-[13px]">
            <input v-model="editForm.is_active" type="checkbox" class="h-4 w-4 accent-brand" />
            Account is active
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" :disabled="editSaving" @click="editOpen = false">Cancel</Button>
          <Button :disabled="editSaving || !editForm.full_name.trim()" @click="saveUser">
            {{ editSaving ? 'Saving…' : 'Save changes' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="passwordOpen">
      <DialogContent class="max-w-md">
        <DialogHeader>
          <DialogTitle>Reset password</DialogTitle>
          <DialogDescription>{{ passwordUser?.full_name }} · {{ passwordUser?.email }}</DialogDescription>
        </DialogHeader>
        <div class="space-y-1.5">
          <Label for="admin-reset-password">New password</Label>
          <Input id="admin-reset-password" v-model="passwordValue" type="password" />
        </div>
        <DialogFooter>
          <Button variant="outline" :disabled="passwordSaving" @click="passwordOpen = false">Cancel</Button>
          <Button :disabled="passwordSaving || passwordValue.length < 8" @click="resetPassword">
            {{ passwordSaving ? 'Saving…' : 'Reset password' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <Dialog v-model:open="departmentOpen">
      <DialogContent class="max-w-md">
        <DialogHeader>
          <DialogTitle>New department</DialogTitle>
          <DialogDescription>Assign users and route documents and meetings to this department.</DialogDescription>
        </DialogHeader>
        <div class="space-y-3">
          <div class="space-y-1.5">
            <Label for="admin-department-code">Code</Label>
            <Input id="admin-department-code" v-model="departmentForm.department_code" placeholder="e.g. CS" />
          </div>
          <div class="space-y-1.5">
            <Label for="admin-department-name">Name</Label>
            <Input id="admin-department-name" v-model="departmentForm.name" />
          </div>
          <div class="space-y-1.5">
            <Label for="admin-department-faculty">Faculty</Label>
            <Input id="admin-department-faculty" v-model="departmentForm.faculty" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" :disabled="departmentSaving" @click="departmentOpen = false">Cancel</Button>
          <Button :disabled="departmentSaving || !departmentForm.department_code.trim() || !departmentForm.name.trim() || !departmentForm.faculty.trim()" @click="createDepartment">
            {{ departmentSaving ? 'Creating…' : 'Create department' }}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
