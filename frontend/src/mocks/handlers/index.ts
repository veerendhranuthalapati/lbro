import { authHandlers }           from './auth'
import { incidentHandlers }       from './incidents'
import { evidenceHandlers }       from './evidence'
import { notificationHandlers }   from './notifications'
import { complianceHandlers }     from './compliance'
import { userHandlers }           from './users'
import { mlHandlers }             from './ml'
import { auditHandlers }          from './audit'
import { infrastructureHandlers } from './infrastructure'
import { dashboardHandlers }      from './dashboard'
import { reportHandlers }         from './reports'

export const handlers = [
  ...authHandlers,
  ...incidentHandlers,
  ...evidenceHandlers,
  ...notificationHandlers,
  ...complianceHandlers,
  ...userHandlers,
  ...mlHandlers,
  ...auditHandlers,
  ...infrastructureHandlers,
  ...dashboardHandlers,
  ...reportHandlers,
]
