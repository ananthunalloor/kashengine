import type { ComponentProps, ReactNode } from "react";
import { LuSearch } from "react-icons/lu";

export function TableFilters({ children, ...props }: ComponentProps<"form">) {
  return (
    <form {...props} className="table-filters">
      {children}
    </form>
  );
}

export function TableFilterField({
  label,
  htmlFor,
  search = false,
  showLabel = false,
  children,
}: {
  label: string;
  htmlFor: string;
  search?: boolean;
  showLabel?: boolean;
  children: ReactNode;
}) {
  return (
    <div className={search ? "table-search" : "table-filter-field"}>
      {search && <LuSearch aria-hidden="true" />}
      <label className={showLabel ? undefined : "sr-only"} htmlFor={htmlFor}>
        {label}
      </label>
      {children}
    </div>
  );
}
