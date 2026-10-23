import { Alert, Anchor, Button, Group, Stack, Text, Title } from "@mantine/core";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "@tanstack/react-router";
import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  LuActivity,
  LuCircleAlert,
  LuDownload,
  LuPlay,
  LuRefreshCw,
  LuSave,
  LuSettings2,
  LuTrash2,
  LuUpload,
} from "react-icons/lu";

import type {
  OpsActionResult,
  OpsField,
  OpsForm,
  OpsPage,
  OpsRow,
  OpsTable,
} from "../../shared/api/opsWorkspace";
import { opsPageQuery, submitOpsForm } from "../../shared/api/opsWorkspace";
import type { OpsSearch } from "../../shared/api/opsWorkspace";
import { AppError, AppLoading } from "../../shared/ui/AppStatus";
import { DataTable } from "../../shared/ui/DataTable";
import { usePageTitle } from "../../shared/ui/usePageTitle";
import { opsPageIcon } from "../../shared/ui/OpsNavigation";
import { OpsTime } from "./OpsTime";
import { notifyOpsMessages, OpsNotice, OpsStatus } from "./OpsStatus";
import { notifyError } from "../../shared/ui/notifications";
import { AppLink } from "../../shared/ui/AppLink";
import { TableFilterField, TableFilters } from "../../shared/ui/TableFilters";

function Field({ field, disabled }: { field: OpsField; disabled: boolean }) {
  const id = useId();
  const common = {
    id,
    name: field.name,
    required: field.required,
    disabled,
    "aria-invalid": field.errors.length > 0 || undefined,
    "aria-describedby": `${id}-help`,
  };
  if (field.kind === "hidden") return <input type="hidden" name={field.name} value={field.value} />;
  return (
    <div className={`ops-field ${field.kind === "checkbox" ? "ops-checkbox" : ""}`}>
      <label htmlFor={id}>{field.label}</label>
      {field.kind === "select" ? (
        <select {...common} defaultValue={field.value}>
          {field.choices.map((choice) => (
            <option key={choice.value} value={choice.value}>
              {choice.label}
            </option>
          ))}
        </select>
      ) : field.kind === "textarea" ? (
        <textarea
          {...common}
          defaultValue={field.value}
          maxLength={field.max_length ?? undefined}
          rows={4}
        />
      ) : field.kind === "checkbox" ? (
        <input
          {...common}
          type="checkbox"
          value={field.value || "on"}
          defaultChecked={field.checked}
        />
      ) : (
        <input
          {...common}
          type={field.kind}
          defaultValue={field.kind === "file" ? undefined : field.value}
          autoComplete={field.kind === "password" ? "new-password" : "off"}
          min={field.min ?? undefined}
          max={field.max ?? undefined}
          step={field.step ?? (field.kind === "number" ? "any" : undefined)}
          maxLength={field.max_length ?? undefined}
          accept={
            field.kind === "file"
              ? ".json,.enc,application/json,application/octet-stream"
              : undefined
          }
        />
      )}
      <div id={`${id}-help`} className="ops-field-help">
        {field.help}
        {field.errors.map((error, index) => (
          <p key={index} role="alert" className="ops-form-error">
            <LuCircleAlert aria-hidden="true" />
            {error}
          </p>
        ))}
      </div>
    </div>
  );
}

export function OpsActionForm({
  form,
  onResult,
}: {
  form: OpsForm;
  onResult: (result: OpsActionResult) => Promise<void>;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  const lock = useRef(false);
  const ActionIcon = form.download
    ? LuDownload
    : form.action.endsWith("/import/")
      ? LuUpload
      : form.action.endsWith("/delete/")
        ? LuTrash2
        : form.action.endsWith("/run/")
          ? LuPlay
          : LuSave;
  return (
    <form
      className="ops-action-form"
      key={version}
      onSubmit={async (event) => {
        event.preventDefault();
        if (lock.current || form.disabled) return;
        if (form.confirmation && !window.confirm(form.confirmation)) return;
        const element = event.currentTarget;
        const payload = new FormData(element);
        lock.current = true;
        setPending(true);
        setError("");
        try {
          const result = await submitOpsForm(form, payload);
          notifyOpsMessages(result.messages);
          if (!result.ok && !result.messages.length) {
            notifyError(new Error("Nothing was saved. Fix the marked fields."), "Action failed");
          }
          element
            .querySelectorAll<HTMLInputElement>("input[type=password],input[type=file]")
            .forEach((input) => {
              input.value = "";
            });
          await onResult(result);
          if (result.ok) setVersion((value) => value + 1);
        } catch (error) {
          notifyError(error, "Action failed");
          element.querySelectorAll<HTMLInputElement>("input[type=password]").forEach((input) => {
            input.value = "";
          });
          setError(
            error instanceof Error
              ? error.message
              : "Action failed. Check the audit trail before retrying.",
          );
        } finally {
          Array.from(payload.keys()).forEach((key) => payload.delete(key));
          lock.current = false;
          setPending(false);
        }
      }}
    >
      <fieldset disabled={pending || form.disabled}>
        <legend className="sr-only">{form.label}</legend>
        <div className="ops-form-fields">
          {form.fields.map((field, index) => (
            <Field
              key={`${field.name}-${index}`}
              field={field}
              disabled={pending || form.disabled}
            />
          ))}
        </div>
        {form.errors.map((error, index) => (
          <p key={index} role="alert" className="ops-form-error">
            <LuCircleAlert aria-hidden="true" />
            {error}
          </p>
        ))}
        <Button
          type="submit"
          disabled={pending || form.disabled}
          color={form.action.endsWith("/delete/") ? "red" : undefined}
          leftSection={<ActionIcon aria-hidden="true" />}
        >
          {pending ? "Working..." : form.label}
        </Button>
      </fieldset>
      {error && (
        <Alert role="alert" color="red" title="Action failed" icon={<LuCircleAlert />}>
          {error}
        </Alert>
      )}
    </form>
  );
}

function WorkspaceTable({
  table,
  label,
  filters,
  onFilter,
  onResult,
  filterControls,
}: {
  table: OpsTable;
  label: string;
  filters: OpsSearch;
  onFilter: (search: OpsSearch) => void;
  onResult: (result: OpsActionResult) => Promise<void>;
  filterControls?: ReactNode;
}) {
  const columns = table.columns.map((column) => ({
    id: column.key,
    label: column.label,
    value: (row: OpsRow) => row.cells[column.key]?.value ?? row.cells[column.key]?.text ?? null,
    render: (row: OpsRow) => {
      const value = row.cells[column.key];
      if (!value) return "\u2013";
      const content =
        value.kind === "time" ? <OpsTime value={value.text || null} /> : value.text || "\u2013";
      const display =
        value.tone === "neutral" ? content : <OpsStatus tone={value.tone}>{content}</OpsStatus>;
      return (
        <span className="ops-cell">
          {value.href ? <AppLink href={value.href}>{display}</AppLink> : display}
        </span>
      );
    },
  }));
  const hasActions = table.rows.some((row) => row.forms.length || row.links.length);
  return (
    <DataTable
      data={table.rows}
      label={label}
      filterControls={filterControls}
      columns={[
        ...columns,
        ...(hasActions
          ? [
              {
                id: "actions",
                label: "Actions",
                sortable: false,
                value: () => null,
                render: (row: OpsRow) => (
                  <div className="ops-row-actions">
                    {row.links.map((link) => (
                      <AppLink key={link.url} href={link.url}>
                        {link.label}
                      </AppLink>
                    ))}
                    {row.forms.map((form) =>
                      form.fields.some(
                        (field) => field.kind !== "hidden" && field.kind !== "checkbox",
                      ) ? (
                        <details key={form.id}>
                          <summary>{form.label}</summary>
                          <OpsActionForm form={form} onResult={onResult} />
                        </details>
                      ) : (
                        <OpsActionForm key={form.id} form={form} onResult={onResult} />
                      ),
                    )}
                  </div>
                ),
              },
            ]
          : []),
      ]}
      filters={
        table.server
          ? []
          : table.filters.map((label) => ({
              label,
              value: (row: OpsRow) => row.cells[label]?.text ?? "",
              options: [...new Set(table.rows.map((row) => row.cells[label]?.text ?? ""))],
            }))
      }
      server={
        table.server
          ? {
              page: table.page,
              pages: table.pages,
              total: table.total,
              pageSize: table.page_size,
              sort: filters.sort,
              onSort: (sort) => onFilter({ ...filters, sort, page: 1 }),
              onPageSize: (page_size) => onFilter({ ...filters, page_size, page: 1 }),
              paginationLabel: `${label} pages`,
              pageLink: (page, label) => (
                <button type="button" onClick={() => onFilter({ ...filters, page })}>
                  {label}
                </button>
              ),
            }
          : undefined
      }
    />
  );
}

export function Workspace({
  path,
  filters,
  onFilter,
}: {
  path: string;
  filters: OpsSearch;
  onFilter: (search: OpsSearch) => void;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const query = useQuery(opsPageQuery(path, filters));
  const [result, setResult] = useState<OpsActionResult | null>(null);
  const [invalidPage, setInvalidPage] = useState<OpsPage | null>(null);
  const [draft, setDraft] = useState(filters.q);
  const scope = JSON.stringify([path, filters]);
  useEffect(() => {
    setResult(null);
    setInvalidPage(null);
    setDraft(filters.q);
  }, [scope]);
  const data = invalidPage ?? query.data;
  const PageIcon = opsPageIcon(path);
  usePageTitle(data?.title ?? "Operations");
  async function onResult(result: OpsActionResult) {
    setResult(result);
    if (result.page) {
      setInvalidPage(result.page);
      return;
    }
    if (!result.ok) return;
    setInvalidPage(null);
    if (result.redirect === "/login/") {
      queryClient.clear();
      window.location.assign("/login/");
      return;
    }
    await queryClient.invalidateQueries({ queryKey: ["app", "ops"] });
    await queryClient.invalidateQueries({ queryKey: ["app", "session"] });
    if (result.redirect && result.redirect !== window.location.pathname) {
      await router.navigate({
        href: result.redirect,
        state: (previous) => ({ ...previous, opsNotice: result.messages }),
      });
      return;
    }
    await router.invalidate();
  }
  if (query.error)
    return (
      <AppError
        error={query.error}
        reset={() => void query.refetch()}
        onRetry={() => void query.refetch()}
        withinShell
        section="Operations"
      />
    );
  if (!data) return <AppLoading withinShell label="operations" />;
  const mainTable = data.sections.find((section) => section.table?.server)?.table;
  const filterControls = (mainTable || path === "logs/" || path === "logins/") && (
    <TableFilters
      onSubmit={(event) => {
        event.preventDefault();
        onFilter({ ...filters, q: draft, page: 1 });
      }}
    >
      <TableFilterField search label={`Search ${data.title}`} htmlFor="ops-q">
        <input
          id="ops-q"
          type="search"
          value={draft}
          maxLength={200}
          placeholder="Search records..."
          onChange={(event) => setDraft(event.target.value)}
        />
      </TableFilterField>
      {mainTable?.filters.map((key) => (
        <TableFilterField key={key} label={key} htmlFor={`ops-filter-${key}`}>
          <select
            id={`ops-filter-${key}`}
            value={filters[key as keyof OpsSearch] ?? ""}
            onChange={(event) => onFilter({ ...filters, [key]: event.target.value, page: 1 })}
          >
            <option value="">All {key.toLowerCase()}</option>
            {mainTable.filter_choices[key]?.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </TableFilterField>
      ))}
      {path === "logins/" && (
        <TableFilterField label="Time window" htmlFor="ops-hours">
          <select
            id="ops-hours"
            value={filters.hours}
            onChange={(event) =>
              onFilter({ ...filters, hours: event.target.value as OpsSearch["hours"], page: 1 })
            }
          >
            <option value="">All time</option>
            <option value="24">Last 24 hours</option>
            <option value="168">Last 7 days</option>
            <option value="720">Last 30 days</option>
          </select>
        </TableFilterField>
      )}
      {path === "logs/" && (
        <>
          <TableFilterField label="Minimum level" htmlFor="ops-level">
            <select
              id="ops-level"
              value={filters.level}
              onChange={(event) => onFilter({ ...filters, level: event.target.value })}
            >
              <option value="">All levels</option>
              {["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </TableFilterField>
          <TableFilterField label="Logger contains" htmlFor="ops-logger">
            <input
              id="ops-logger"
              name="logger"
              defaultValue={filters.logger}
              placeholder="Logger contains..."
              onBlur={(event) => onFilter({ ...filters, logger: event.target.value })}
            />
          </TableFilterField>
          <TableFilterField showLabel label="Tail entries (1–1000)" htmlFor="ops-limit">
            <input
              id="ops-limit"
              type="number"
              min={1}
              max={1000}
              defaultValue={filters.limit}
              onBlur={(event) => {
                if (event.target.validity.valid)
                  onFilter({ ...filters, limit: Number(event.target.value) });
              }}
            />
          </TableFilterField>
          <label>
            <input
              type="checkbox"
              checked={filters.live === "true"}
              onChange={(event) =>
                onFilter({ ...filters, live: event.target.checked ? "true" : "" })
              }
            />{" "}
            Live updates (visible tab only)
          </label>
        </>
      )}
      <Button type="submit">Search</Button>
    </TableFilters>
  );
  return (
    <Stack gap="xl" className="ops-workspace">
      <header>
        <Text className="app-eyebrow">
          <LuSettings2 aria-hidden="true" /> Operations
        </Text>
        <Title order={1} className="ops-page-title">
          <PageIcon aria-hidden="true" />
          {data.title}
        </Title>
        <Text c="dimmed" mt="sm">
          {data.description}
        </Text>
        <Group mt="sm">
          <Button
            variant="default"
            onClick={() => {
              setInvalidPage(null);
              void query.refetch();
            }}
            leftSection={<LuRefreshCw aria-hidden="true" />}
          >
            Refresh
          </Button>
        </Group>
      </header>
      {result && (
        <>
          <OpsNotice messages={result.messages} />
          {!result.ok && !result.messages.length && (
            <Alert role="alert" color="red" icon={<LuCircleAlert />}>
              Nothing was saved. Fix the marked fields.
            </Alert>
          )}
        </>
      )}
      {!mainTable && filterControls && (
        <div className="data-panel table-toolbar">{filterControls}</div>
      )}
      {data.refresh_seconds > 0 && (
        <Text size="sm" c="dimmed">
          <LuActivity aria-hidden="true" />{" "}
          {path === "logs/"
            ? "Logs update live while visible; pauses on errors."
            : "Updates live as jobs and data change."}
        </Text>
      )}
      {data.sections.map((section, index) => (
        <section key={`${scope}-${index}`} className="ops-section">
          <Title order={2} className="ops-section-title">
            <PageIcon aria-hidden="true" /> {section.title}
          </Title>
          {section.description && (
            <Text c="dimmed" size="sm">
              {section.description}
            </Text>
          )}
          {section.chart.length > 0 && (
            <figure className="ops-chart">
              <figcaption className="ops-chart-legend">
                <span>
                  <i className="ops-legend-total" /> Total
                </span>
                <span className="ops-tone-negative">
                  <i className="ops-legend-failed" /> Failed / alerts
                </span>
              </figcaption>
              <svg
                className="ops-series"
                viewBox={`0 0 ${section.chart.length * 32} 130`}
                role="img"
                aria-label={`${section.title}: daily totals and failures. Exact values in the table below.`}
              >
                {section.chart.map((point, index) => {
                  const max = Math.max(
                    1,
                    ...section.chart.map((point) => Math.max(point.value, point.failed)),
                  );
                  const height = (100 * point.value) / max;
                  const failedHeight = (100 * point.failed) / max;
                  return (
                    <g key={point.label}>
                      <title>
                        {point.label}: {point.value} total, {point.failed} failed
                      </title>
                      <rect
                        x={index * 32 + 3}
                        y={105 - height}
                        width={12}
                        height={height}
                        className="ops-bar-value"
                      />
                      <rect
                        x={index * 32 + 16}
                        y={105 - failedHeight}
                        width={10}
                        height={failedHeight}
                        className="ops-bar-failed"
                      />
                      <text x={index * 32 + 14} y={122} textAnchor="middle">
                        {point.label}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </figure>
          )}
          {!!Object.keys(section.details).length && (
            <dl className="ops-detail-grid">
              {Object.entries(section.details).map(([label, value]) => (
                <div key={label} className={`ops-stat ops-stat-${value.tone}`}>
                  <dt>{label}</dt>
                  <dd>
                    {value.kind === "time" ? (
                      <OpsTime value={value.text} />
                    ) : value.tone !== "neutral" ? (
                      <OpsStatus tone={value.tone}>{value.text || "\u2013"}</OpsStatus>
                    ) : (
                      value.text || "\u2013"
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          {section.links.map((link) => (
            <Anchor component={AppLink} key={link.url} href={link.url}>
              {link.label}
            </Anchor>
          ))}
          {section.table && (
            <WorkspaceTable
              table={section.table}
              label={section.title}
              filters={filters}
              onFilter={onFilter}
              onResult={onResult}
              filterControls={section.table === mainTable ? filterControls : undefined}
            />
          )}
          {section.forms.map((form) => (
            <OpsActionForm
              key={`${form.id}-${invalidPage ? "invalid" : "saved"}`}
              form={form}
              onResult={onResult}
            />
          ))}
        </section>
      ))}
    </Stack>
  );
}
