import { TeamWorkspace } from './TeamWorkspace';
import type { MissionControlProps } from './types';
export type { AgentEvent, AgentEventStatus, AgentEventType, MissionControlProps, MissionContext, MissionNavigationTarget } from './types';
export function MissionControl(props: MissionControlProps) { return <TeamWorkspace {...props} />; }
export default MissionControl;