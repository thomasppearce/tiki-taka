"use client";

import { Segmented } from "@/components/ui/Segmented";
import { ROLES, type Role, useRole } from "@/lib/role";

/** Guest / Fan / Producer. Accounts are simulated, so anyone can switch. */
export function RoleSwitch() {
  const [role, setRole] = useRole();
  return (
    <Segmented
      label="View as"
      value={role}
      onChange={setRole}
      options={(Object.keys(ROLES) as Role[]).map((value) => ({
        value,
        label: ROLES[value].label,
      }))}
    />
  );
}
