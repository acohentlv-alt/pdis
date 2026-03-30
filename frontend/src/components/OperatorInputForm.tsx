import { useState, useEffect } from 'react';
import { useOperatorInput } from '../api/queries';
import { useSaveOperatorInput } from '../api/mutations';

interface OperatorInputFormProps {
  yad2Id: string;
}

export default function OperatorInputForm({ yad2Id }: OperatorInputFormProps) {
  const { data } = useOperatorInput(yad2Id);
  const save = useSaveOperatorInput(yad2Id);

  const [agentName, setAgentName] = useState('');
  const [manualDom, setManualDom] = useState('');
  const [flexibility, setFlexibility] = useState('');
  const [condition, setCondition] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) {
      setAgentName((data.agent_name as string) ?? '');
      setManualDom(data.manual_days_on_market != null ? String(data.manual_days_on_market) : '');
      setFlexibility((data.flexibility as string) ?? '');
      setCondition((data.condition as string) ?? '');
    }
  }, [data]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    save.mutate(
      {
        agent_name: agentName || null,
        manual_days_on_market: manualDom ? parseInt(manualDom, 10) : null,
        flexibility: flexibility || null,
        condition: condition || null,
      },
      {
        onSuccess: () => {
          setSaved(true);
          setTimeout(() => setSaved(false), 2000);
        },
      }
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Agent name</label>
        <input
          type="text"
          value={agentName}
          onChange={e => setAgentName(e.target.value)}
          placeholder="e.g. Moshe"
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Manual days on market</label>
        <input
          type="number"
          value={manualDom}
          onChange={e => setManualDom(e.target.value)}
          placeholder="e.g. 45"
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Flexibility</label>
        <select
          value={flexibility}
          onChange={e => setFlexibility(e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
        >
          <option value="">Unknown</option>
          <option value="High">High</option>
          <option value="Medium">Medium</option>
          <option value="Low">Low</option>
        </select>
      </div>
      <div>
        <label className="block text-xs font-medium text-gray-600 mb-1">Condition</label>
        <select
          value={condition}
          onChange={e => setCondition(e.target.value)}
          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
        >
          <option value="">Unknown</option>
          <option value="Needs Renovation">Needs Renovation</option>
          <option value="Fair">Fair</option>
          <option value="Good">Good</option>
          <option value="Excellent">Excellent</option>
        </select>
      </div>
      <button
        type="submit"
        disabled={save.isPending}
        className="w-full min-h-[44px] bg-gray-900 text-white rounded-lg text-sm font-medium disabled:opacity-50"
      >
        {save.isPending ? 'Saving…' : saved ? '✓ Saved' : 'Save'}
      </button>
    </form>
  );
}
