import { useState, useCallback, type ReactElement } from "react";
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  rectSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { cn } from "../../lib/utils";

interface SortableItemProps {
  id: string;
  children: ReactElement;
  className?: string;
}

function SortableItem({ id, children, className }: SortableItemProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(isDragging && "opacity-40 z-50", className)}
      {...attributes}
      {...listeners}
    >
      {children}
    </div>
  );
}

interface DraggableGridProps {
  children: ReactElement[];
  storageKey: string;
  baseGridClass: string;
}

export function DraggableGrid({ children, storageKey, baseGridClass }: DraggableGridProps) {
  const [isEditing, setIsEditing] = useState(false);

  const itemIds = children.map((_, i) => `${storageKey}-item-${i}`);
  const [order, setOrder] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) return JSON.parse(raw) as string[];
    } catch {
      // ignore
    }
    return itemIds;
  });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    setOrder((prev) => {
      const oldIdx = prev.indexOf(String(active.id));
      const newIdx = prev.indexOf(String(over.id));
      if (oldIdx === -1 || newIdx === -1) return prev;

      const next = [...prev];
      next.splice(oldIdx, 1);
      next.splice(newIdx, 0, String(active.id));
      try {
        localStorage.setItem(storageKey, JSON.stringify(next));
      } catch {
        // ignore
      }
      return next;
    });
  }, [storageKey]);

  // Map children to their sorted positions
  const sortedChildren = order.map((id) => {
    const idx = itemIds.indexOf(id);
    return idx !== -1 ? children[idx] : null;
  }).filter(Boolean) as ReactElement[];

  return (
    <div>
      <div className="flex justify-end mb-2">
        <button
          onClick={() => setIsEditing((v) => !v)}
          className={cn(
            "text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-md border transition-colors",
            isEditing
              ? "bg-accent-blue/10 text-accent-blue border-accent-blue/30"
              : "text-text-muted border-border-subtle hover:text-text-secondary hover:border-border-strong"
          )}
        >
          {isEditing ? "Lock Layout" : "Edit Layout"}
        </button>
      </div>
      {isEditing ? (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={order} strategy={rectSortingStrategy}>
            <div className={baseGridClass}>
              {sortedChildren.map((child, i) => {
                const id = order[i];
                return (
                  <SortableItem key={id} id={id}>
                    {child}
                  </SortableItem>
                );
              })}
            </div>
          </SortableContext>
        </DndContext>
      ) : (
        <div className={baseGridClass}>
          {sortedChildren}
        </div>
      )}
    </div>
  );
}
