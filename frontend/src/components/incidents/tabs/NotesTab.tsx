import { useState } from 'react'
import { Edit3, Trash2, Plus, FileText } from 'lucide-react'
import { useInvestigationNotes, useAddNote, useUpdateNote, useDeleteNote } from '@/hooks/useApi'
import { formatDate, timeAgo } from '@/utils'
import { ORANGE, BLACK, BORDER, GRAY, CREAM, PARCH, GREEN, Card, CardHead, Skeleton } from '../WorkspaceShared'

interface Props { incidentId: string }

export function NotesTab({ incidentId }: Props) {
  const { data, isLoading } = useInvestigationNotes(incidentId)
  const addNote    = useAddNote()
  const updateNote = useUpdateNote()
  const deleteNote = useDeleteNote()

  const notes = data?.notes ?? []

  const [draft,    setDraft]    = useState('')
  const [editId,   setEditId]   = useState<string | null>(null)
  const [editText, setEditText] = useState('')

  const handleAdd = () => {
    const content = draft.trim()
    if (!content) return
    addNote.mutate({ incidentId, content }, { onSuccess: () => setDraft('') })
  }

  const startEdit = (id: string, current: string) => {
    setEditId(id)
    setEditText(current)
  }

  const handleUpdate = () => {
    if (!editId) return
    updateNote.mutate(
      { incidentId, noteId: editId, content: editText.trim() },
      { onSuccess: () => { setEditId(null); setEditText('') } }
    )
  }

  const handleDelete = (noteId: string) => {
    if (!confirm('Delete this note?')) return
    deleteNote.mutate({ incidentId, noteId })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

      {/* Add note */}
      <Card>
        <CardHead icon={<Plus style={{ width: 13, height: 13, color: GREEN }} />} title="Add Investigation Note" />
        <textarea
          value={draft}
          onChange={e => setDraft(e.target.value)}
          placeholder="Document findings, observations, or next steps…"
          rows={4}
          style={{
            width: '100%', boxSizing: 'border-box',
            fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: BLACK,
            background: PARCH, border: `1px solid ${BORDER}`, borderRadius: 3,
            padding: '10px 12px', resize: 'vertical',
            outline: 'none', lineHeight: 1.6,
          }}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
          <button
            onClick={handleAdd}
            disabled={!draft.trim() || addNote.isPending}
            style={{
              fontSize: 10, color: '#fff', background: ORANGE, border: 'none',
              borderRadius: 2, padding: '7px 16px', cursor: 'pointer',
              opacity: !draft.trim() || addNote.isPending ? 0.5 : 1,
              textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600,
            }}
          >
            {addNote.isPending ? 'Saving…' : 'Save Note'}
          </button>
        </div>
      </Card>

      {/* Notes list */}
      <Card>
        <CardHead
          icon={<FileText style={{ width: 13, height: 13, color: ORANGE }} />}
          title="Investigation Notes"
          extra={<span style={{ fontSize: 9, color: GRAY }}>{notes.length} notes</span>}
        />

        {isLoading ? <Skeleton lines={4} />
          : notes.length === 0 ? <p style={{ fontSize: 11, color: GRAY }}>No notes yet. Add your first observation above.</p>
          : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {notes.map(note => (
                <div key={note.id} style={{ border: `1px solid ${BORDER}`, borderRadius: 4, overflow: 'hidden' }}>
                  {/* Author + timestamp */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '7px 12px', background: PARCH }}>
                    <div>
                      <span style={{ fontSize: 10, fontWeight: 600, color: BLACK }}>
                        {note.author_name ?? note.author_email ?? 'Unknown analyst'}
                      </span>
                      {note.author_email && note.author_name && (
                        <span style={{ fontSize: 9, color: GRAY, marginLeft: 6 }}>· {note.author_email}</span>
                      )}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 9, color: GRAY }}>{timeAgo(note.created_at)}</span>
                      {note.updated_at !== note.created_at && (
                        <span style={{ fontSize: 9, color: GRAY, fontStyle: 'italic' }}>edited</span>
                      )}
                      <button
                        onClick={() => startEdit(note.id, note.content)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: GRAY, padding: 2 }}
                        title="Edit note"
                      >
                        <Edit3 style={{ width: 11, height: 11 }} />
                      </button>
                      <button
                        onClick={() => handleDelete(note.id)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', padding: 2 }}
                        title="Delete note"
                      >
                        <Trash2 style={{ width: 11, height: 11 }} />
                      </button>
                    </div>
                  </div>

                  {/* Content or edit form */}
                  {editId === note.id ? (
                    <div style={{ padding: 12 }}>
                      <textarea
                        value={editText}
                        onChange={e => setEditText(e.target.value)}
                        rows={4}
                        style={{
                          width: '100%', boxSizing: 'border-box',
                          fontFamily: 'JetBrains Mono, monospace', fontSize: 11, color: BLACK,
                          background: PARCH, border: `1px solid ${ORANGE}60`, borderRadius: 3,
                          padding: '8px 10px', resize: 'vertical', outline: 'none', lineHeight: 1.6,
                        }}
                      />
                      <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
                        <button
                          onClick={handleUpdate}
                          disabled={!editText.trim() || updateNote.isPending}
                          style={{ fontSize: 9, color: '#fff', background: GREEN, border: 'none', borderRadius: 2, padding: '5px 12px', cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '0.07em' }}
                        >
                          {updateNote.isPending ? 'Saving…' : 'Save'}
                        </button>
                        <button
                          onClick={() => { setEditId(null); setEditText('') }}
                          style={{ fontSize: 9, color: GRAY, background: 'white', border: `1px solid ${BORDER}`, borderRadius: 2, padding: '5px 12px', cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '0.07em' }}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div style={{ padding: '10px 12px' }}>
                      <p style={{ fontSize: 12, color: BLACK, lineHeight: 1.7, margin: 0, whiteSpace: 'pre-wrap' }}>
                        {note.content}
                      </p>
                    </div>
                  )}

                  {/* Timestamps */}
                  <div style={{ padding: '4px 12px 6px', borderTop: `1px solid ${PARCH}` }}>
                    <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 8, color: GRAY }}>
                      Created {formatDate(note.created_at)}
                      {note.updated_at !== note.created_at && ` · Updated ${formatDate(note.updated_at)}`}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )
        }
      </Card>
    </div>
  )
}
