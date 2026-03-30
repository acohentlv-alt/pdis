import { useState } from 'react';
import { useAddNote, useDeleteNote } from '../api/mutations';
import { formatDate } from '../lib/format';

interface Note {
  id: number;
  note: string;
  created_by: string;
  created_at: string;
}

interface NotesListProps {
  yad2Id: string;
  notes: Note[];
}

export default function NotesList({ yad2Id, notes }: NotesListProps) {
  const [text, setText] = useState('');
  const addNote = useAddNote(yad2Id);
  const deleteNote = useDeleteNote();

  function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    addNote.mutate({ note: text.trim() }, {
      onSuccess: () => setText(''),
    });
  }

  return (
    <div className="space-y-3">
      {notes.length === 0 && (
        <p className="text-sm text-gray-400">No notes yet.</p>
      )}
      {notes.map(n => (
        <div key={n.id} className="flex items-start justify-between gap-2 bg-gray-50 rounded-lg p-3">
          <div className="flex-1 min-w-0">
            <p className="text-sm text-gray-800 break-words" dir="auto">{n.note}</p>
            <p className="text-xs text-gray-400 mt-1">
              {n.created_by} · {formatDate(n.created_at)}
            </p>
          </div>
          <button
            onClick={() => deleteNote.mutate({ noteId: n.id, yad2Id })}
            className="shrink-0 text-gray-300 hover:text-red-400 text-lg leading-none mt-0.5"
            aria-label="Delete note"
          >
            ×
          </button>
        </div>
      ))}

      <form onSubmit={handleAdd} className="flex gap-2">
        <input
          type="text"
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder="Add a note…"
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={addNote.isPending || !text.trim()}
          className="min-h-[44px] px-4 bg-gray-900 text-white rounded-lg text-sm font-medium disabled:opacity-50"
        >
          Add
        </button>
      </form>
    </div>
  );
}
