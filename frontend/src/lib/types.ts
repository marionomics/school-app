export interface User {
  id: number;
  email: string;
  name: string;
  username: string | null;
  bio: string;
  avatar_url: string | null;
  role: "student" | "teacher";
  grade_is_private: boolean;
}

export interface ScheduleBlock {
  day: number; // 0 = lunes
  start: string; // "HH:MM"
  end: string;
}

export interface ClassOut {
  id: number;
  name: string;
  code: string;
  teacher_id: number;
  start_date: string;
  end_date: string;
  schedule: ScheduleBlock[];
  tareas_weight: number;
  examenes_weight: number;
  attendance_required_pct: number;
}

export interface MyClasses {
  teaching: ClassOut[];
  enrolled: ClassOut[];
}

export interface AuthResponse {
  token: string;
  user: User;
  needs_onboarding: boolean;
}

export interface Author {
  id: number;
  username: string | null;
  name: string;
  avatar_url: string | null;
  role: "student" | "teacher";
}

export interface Attachment {
  id: number;
  file_name: string;
  mime_type: string;
}

export interface Post {
  id: number;
  author: Author;
  type: "regular" | "participacion" | "tarea" | "examen";
  class_id: number | null;
  class_name: string | null;
  content: string;
  taps: number | null;
  status: "active" | "deleted" | "vetoed";
  like_count: number;
  reply_count: number;
  liked_by_me: boolean;
  attachments: Attachment[];
  created_at: string;
  last_activity_at: string;
  parent_id: number | null;
  due_date: string | null;
  is_entrega: boolean;
}

export interface FeedPage {
  items: Post[];
  next_cursor: string | null;
}

export interface ThreadResponse {
  post: Post;
  replies: Post[];
}

export interface GradeEvent {
  source_type: string;
  points: number;
  note: string | null;
  created_at: string;
}

export interface Rubro {
  evaluated: boolean;
  points: number;
  weight: number;
  count_due: number;
  count_entregadas: number;
}

export interface LedgerBreakdown {
  participaciones: number;
  likes: number;
  likes_count: number;
  other: number;
}

export interface GradeSummary {
  class_id: number;
  class_name: string;
  total: number;
  counts: { participaciones: number; likes_received: number };
  tareas: Rubro;
  examenes: Rubro;
  ledger: LedgerBreakdown;
  faltas: { count: number; points: number };
  events: GradeEvent[];
}
