/**
 * AlertsPanel.tsx | OWNER: Engineer C
 * TODO: implement component UI
 */
export default function AlertsPanel(props: any) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-6">
      <h2 className="text-lg font-semibold mb-4">AlertsPanel</h2>
      <p className="text-gray-400 text-sm">TODO: implement this panel</p>
      <pre className="text-xs text-gray-600 mt-4">{JSON.stringify(props, null, 2)}</pre>
    </div>
  );
}
