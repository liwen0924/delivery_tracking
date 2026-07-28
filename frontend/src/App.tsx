import { ToastProvider } from '@/components/Toaster'
import { ShipmentsPage } from '@/pages/ShipmentsPage'

export default function App() {
  return (
    <ToastProvider>
      <main className="min-h-full">
        <ShipmentsPage />
      </main>
    </ToastProvider>
  )
}
