"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FolderPlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog, Dialog } from "@/components/ui/dialog";
import { Field, Input, Textarea } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import {
  useCreateProject,
  useDeleteProject,
  useUpdateProject,
} from "@/hooks/use-api";
import type { Project } from "@/lib/types";
import { errorMessage } from "@/lib/utils";

interface CreateProjectDialogProps {
  open: boolean;
  onClose: () => void;
  onCreated?: (project: Project) => void;
}

export function CreateProjectDialog({
  open,
  onClose,
  onCreated,
}: CreateProjectDialogProps) {
  const router = useRouter();
  const { toast } = useToast();
  const createProject = useCreateProject();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setName("");
      setDescription("");
      setError(null);
      createProject.reset();
    }
    // The mutation object is recreated per render; resetting only on open is
    // what we want, so the mutation is intentionally omitted.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const submit = () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Give the project a name.");
      return;
    }
    setError(null);
    createProject.mutate(
      { name: trimmed, description: description.trim() || null },
      {
        onSuccess: (project) => {
          toast({
            title: "Project created",
            description: `“${project.name}” is ready for files.`,
            tone: "success",
          });
          onClose();
          if (onCreated) {
            onCreated(project);
          } else {
            router.push(`/projects/${project.id}`);
          }
        },
        onError: (mutationError) => setError(errorMessage(mutationError)),
      },
    );
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="New project"
      description="A project is a separate library of files, chunks and conversations."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={createProject.isPending}>
            Cancel
          </Button>
          <Button
            variant="primary"
            onClick={submit}
            loading={createProject.isPending}
            icon={<FolderPlus className="h-3.5 w-3.5" />}
          >
            Create project
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Name" error={error ?? undefined}>
          <Input
            autoFocus
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. Rika backend"
            maxLength={200}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                submit();
              }
            }}
          />
        </Field>
        <Field
          label="Description"
          hint="Optional. What belongs in this project, and what should Rika know about it?"
        >
          <Textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="The FastAPI service, ingestion pipeline and retrieval code."
            maxLength={2000}
            rows={3}
          />
        </Field>
      </div>
    </Dialog>
  );
}

interface RenameProjectDialogProps {
  project: Project;
  open: boolean;
  onClose: () => void;
}

export function RenameProjectDialog({
  project,
  open,
  onClose,
}: RenameProjectDialogProps) {
  const { toast } = useToast();
  const updateProject = useUpdateProject(project.id);
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description ?? "");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setName(project.name);
      setDescription(project.description ?? "");
      setError(null);
      updateProject.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, project.id, project.name, project.description]);

  const submit = () => {
    const trimmed = name.trim();
    if (!trimmed) {
      setError("Give the project a name.");
      return;
    }
    setError(null);
    updateProject.mutate(
      { name: trimmed, description: description.trim() || null },
      {
        onSuccess: () => {
          toast({ title: "Project updated", tone: "success" });
          onClose();
        },
        onError: (mutationError) => setError(errorMessage(mutationError)),
      },
    );
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Rename project"
      description="Names and descriptions can change without touching the indexed files."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={updateProject.isPending}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} loading={updateProject.isPending}>
            Save changes
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Name" error={error ?? undefined}>
          <Input
            autoFocus
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={200}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                submit();
              }
            }}
          />
        </Field>
        <Field label="Description">
          <Textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            maxLength={2000}
            rows={3}
          />
        </Field>
      </div>
    </Dialog>
  );
}

interface DeleteProjectDialogProps {
  project: Project;
  open: boolean;
  onClose: () => void;
  onDeleted?: () => void;
}

export function DeleteProjectDialog({
  project,
  open,
  onClose,
  onDeleted,
}: DeleteProjectDialogProps) {
  const { toast } = useToast();
  const deleteProject = useDeleteProject();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setError(null);
      deleteProject.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const submit = () => {
    setError(null);
    deleteProject.mutate(project.id, {
      onSuccess: () => {
        toast({
          title: "Project deleted",
          description: `“${project.name}” and its indexed files were removed.`,
          tone: "success",
        });
        onClose();
        onDeleted?.();
      },
      onError: (mutationError) => setError(errorMessage(mutationError)),
    });
  };

  return (
    <ConfirmDialog
      open={open}
      onClose={onClose}
      onConfirm={submit}
      title={`Delete “${project.name}”?`}
      description={
        error ??
        "This removes the project, its uploaded files, chunks, symbols, jobs and conversations. This cannot be undone."
      }
      confirmLabel="Delete project"
      loading={deleteProject.isPending}
    />
  );
}
