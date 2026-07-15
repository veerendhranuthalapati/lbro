import { Outlet } from 'react-router-dom'
import { Sidebar } from '@/components/layout/Sidebar'
import { Navbar } from '@/components/layout/Navbar'
import { ToastContainer } from '@/components/ui/Toast'
import { GlobalSearch } from '@/components/GlobalSearch'
import { useIncidents } from '@/hooks/useApi'

export function AppLayout() {
  const { data: newData }      = useIncidents({ status: 'new',      page_size: 1 })
  const { data: triagingData } = useIncidents({ status: 'triaging', page_size: 1 })
  const alertCount = (newData?.total ?? 0) + (triagingData?.total ?? 0)
  return (
    <div className="flex h-screen overflow-hidden" style={{ background: '#f0ebe2' }}>
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Navbar alertCount={alertCount} />
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
      <ToastContainer />
      <GlobalSearch />
    </div>
  )
}
