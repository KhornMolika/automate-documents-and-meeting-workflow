import { expect, type APIRequestContext, type Page } from '@playwright/test'

const API = 'http://127.0.0.1:8000/api/v1'

export async function loginToken(request: APIRequestContext) {
  const response = await request.post(`${API}/auth/login`, {
    form: { username: 'admin@aub.edu.kh', password: 'Admin@AUB2026' },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  return (await response.json()).access_token as string
}

export async function authenticate(page: Page, request: APIRequestContext) {
  const token = await loginToken(request)
  await page.context().addCookies([
    { name: 'aub_access_token', value: token, url: 'http://127.0.0.1:3000' },
  ])
  return token
}

export async function api<T>(
  request: APIRequestContext,
  token: string,
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  path: string,
  data?: unknown,
): Promise<T> {
  const response = await request.fetch(`${API}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}` },
    data: data as any,
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  return response.json() as Promise<T>
}

export async function currentUser(request: APIRequestContext, token: string) {
  return api<{ id: string, department_id: string, full_name: string }>(request, token, 'GET', '/auth/me')
}

export async function createMeeting(
  request: APIRequestContext,
  token: string,
  title: string,
  start: Date,
  end: Date,
) {
  const user = await currentUser(request, token)
  return api<{ id: string, title: string }>(request, token, 'POST', '/meetings', {
    title,
    description: 'Created by the Playwright E2E suite.',
    scheduled_start: start.toISOString(),
    scheduled_end: end.toISOString(),
    department_id: user.department_id,
    agendas: [
      { item_order: 1, title: 'E2E agenda one', duration_minutes: 15 },
      { item_order: 2, title: 'E2E agenda two', duration_minutes: 20 },
    ],
  })
}

export async function addTranscript(request: APIRequestContext, token: string, meetingId: string) {
  await api(request, token, 'POST', `/meetings/${meetingId}/transcripts`, {
    speaker_label: 'E2E Speaker',
    start_timestamp: 5,
    end_timestamp: 12,
    original_text: 'សូមពិនិត្យសំណើស្រាវជ្រាវនេះ។',
    translated_text: 'Please review this research proposal.',
    confidence_score: 0.95,
    language_detected: 'km-en',
  })
}

function momPayload() {
  return {
    executive_summary: 'The board reviewed the proposal and agreed the next steps.',
    discussion_points: ['Proposal reviewed.', 'Next steps agreed.'],
    decisions: [
      {
        agenda_topic: 'E2E agenda one',
        decision_text: 'Approve the proposal for the next stage.',
        context_notes: null,
      },
    ],
    action_items: [
      {
        task_description: 'Submit the E2E ethics approval.',
        assignee_name: 'E2E Assignee',
        deadline: '2026-12-01',
        confidence_score: 0.95,
      },
    ],
  }
}

export async function endAllActiveMeetings(request: APIRequestContext, token: string) {
  const meetings = await api<{ id: string, status: string }[]>(
    request,
    token,
    'GET',
    '/meetings?limit=200',
  )
  for (const meeting of meetings) {
    if (meeting.status === 'In Progress') {
      await api(request, token, 'POST', `/meetings/${meeting.id}/end`)
    }
  }
}

export async function seedLiveMeeting(request: APIRequestContext, token: string, title: string) {
  await endAllActiveMeetings(request, token)
  const now = Date.now()
  const meeting = await createMeeting(
    request,
    token,
    title,
    new Date(now - 5 * 60_000),
    new Date(now + 55 * 60_000),
  )
  await api(request, token, 'POST', `/meetings/${meeting.id}/start`)
  await addTranscript(request, token, meeting.id)
  return meeting
}

export async function seedDraftMeeting(request: APIRequestContext, token: string, title: string) {
  const meeting = await seedLiveMeeting(request, token, title)
  await api(request, token, 'PUT', `/meetings/${meeting.id}/mom-draft`, momPayload())
  return meeting
}

export async function seedCompletedMeeting(request: APIRequestContext, token: string, title: string) {
  const now = Date.now()
  const meeting = await createMeeting(
    request,
    token,
    title,
    new Date(now - 2 * 3600_000),
    new Date(now - 1 * 3600_000),
  )
  await api(request, token, 'POST', `/meetings/${meeting.id}/start`)
  await addTranscript(request, token, meeting.id)
  await api(request, token, 'PUT', `/meetings/${meeting.id}/mom-draft`, momPayload())
  await api(request, token, 'POST', `/meetings/${meeting.id}/approve-mom`, momPayload())
  return meeting
}

export async function seedDocument(request: APIRequestContext, token: string, title: string) {
  const response = await request.post(`${API}/documents/upload`, {
    headers: { Authorization: `Bearer ${token}` },
    multipart: {
      file: {
        name: `e2e_${Date.now()}.csv`,
        mimeType: 'text/csv',
        buffer: Buffer.from(`Policy,Owner\n${title},Academic Affairs\n`),
      },
      title,
      academic_year: '2026-2027',
    },
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  return response.json() as Promise<{ id: string, title: string }>
}

export function uniqueTitle(prefix: string) {
  return `${prefix} ${Date.now()}-${Math.floor(Math.random() * 1000)}`
}
