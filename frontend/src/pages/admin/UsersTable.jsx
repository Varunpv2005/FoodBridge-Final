import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { PageHeader, ErrorBanner } from '../../components/UI'

const ROLE_COLOR = {
  donor: 'bg-amber-100 text-amber-700', ngo: 'bg-brand-100 text-brand-800',
  volunteer: 'bg-blue-100 text-blue-700', admin: 'bg-purple-100 text-purple-700',
}

export default function UsersTable() {
  const [users, setUsers] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    api.allUsers().then(setUsers).catch((e) => setError(e.message))
  }, [])

  return (
    <div>
      <PageHeader title="Users" subtitle="All registered donors, NGOs, volunteers, and admins." />
      <ErrorBanner message={error} />

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
              <th className="pb-2">Name</th><th className="pb-2">Email</th><th className="pb-2">Role</th>
              <th className="pb-2">Trust score</th><th className="pb-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-b border-gray-50">
                <td className="py-2.5 font-medium text-gray-800">{u.name}</td>
                <td className="py-2.5 text-gray-500">{u.email}</td>
                <td className="py-2.5"><span className={`text-xs px-2 py-1 rounded-full ${ROLE_COLOR[u.role]}`}>{u.role}</span></td>
                <td className="py-2.5 text-gray-600">{u.trust_score?.toFixed(0)}</td>
                <td className="py-2.5 text-gray-500">
                  {u.role === 'volunteer' && (u.volunteer_is_available ? 'Available' : 'On delivery')}
                  {u.role === 'ngo' && `${u.ngo_capacity_available} plates free`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
