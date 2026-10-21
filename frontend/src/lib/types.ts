export interface User {
  id: number;
  email: string;
  name: string;
  username: string | null;
  bio: string;
  avatar_url: string | null;
  has_own_avatar: boolean;
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
  /** Signed link, valid an hour, for images any phone can show. null → chip. */
  url: string | null;
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
  /** A teacher gave this post aura. Everyone sees it. */
  teacher_aura: boolean;
  attachments: Attachment[];
  created_at: string;
  last_activity_at: string;
  parent_id: number | null;
  due_date: string | null;
  is_entrega: boolean;
  examen_mode: "paper" | "digital" | null;
  graded_at: string | null;
  my_review: Review | null;
  veto_reason: string | null;
  /** Feed only: the one comment shown under the card. */
  featured_reply?: Post | null;
}

export interface Review {
  id: number;
  item_post_id: number;
  student_id: number;
  entrega_post_id: number | null;
  score: number | null;
  auto_score: number | null;
  feedback: string | null;
  updated_at: string | null;
}

export interface QueueStudent {
  id: number;
  username: string | null;
  name: string;
}

export interface EntregaRow {
  student: QueueStudent;
  entrega_post_id: number;
  created_at: string;
  auto_score: number | null;
  reviewed: boolean;
  score: number | null;
}

export interface EntregaGroup {
  tarea: { id: number; content: string; due_date: string | null };
  pending: number;
  entregas: EntregaRow[];
}

export interface ExamenListItem {
  id: number;
  content: string;
  examen_mode: "paper" | "digital";
  graded_at: string | null;
  created_at: string;
}

export interface ExamenRoster {
  examen: { id: number; content: string; examen_mode: "paper" | "digital";
            graded_at: string | null };
  rows: {
    student: QueueStudent;
    entrega_post_id: number | null;
    /** Their marked entrega, else their latest reply with files (bug 8). */
    submission: ExamenSubmission | null;
    score: number | null;
  }[];
}

export interface ExamenSubmission {
  post_id: number;
  content: string;
  created_at: string;
  is_entrega: boolean;
  attachments: Attachment[];
}

export interface ParticipacionRow {
  post_id: number;
  student: QueueStudent;
  content: string;
  taps: number | null;
  points: number;
  vetoed: boolean;
  reviewed: boolean;
  veto_reason: string | null;
  created_at: string;
}

export interface Incentive {
  id: number;
  class_id: number;
  name: string;
  points: number;
  description: string | null;
  created_at: string;
  deleted_at: string | null;
}

export interface ClassSettings {
  tareas_weight: number;
  examenes_weight: number;
  tap_value: number;
  like_value: number;
  like_exponent: number;
  attendance_required_pct: number;
}

export interface SessionOut {
  id: number;
  class_id: number;
  date: string;
  opened_at: string | null;
  closed_at: string | null;
  attendance_count: number;
}

export interface RosterStudent {
  id: number;
  name: string;
  username: string | null;
  avatar_url: string | null;
  has_own_avatar: boolean;
  status: "active" | "ghost" | "polizon";
  grade: number;
  faltas: number;
}

export interface MemberOut {
  id: number;
  name: string;
  username: string | null;
  avatar_url: string | null;
  status: "active" | "ghost" | "polizon";
}

export interface ClassDetailWithMembers extends ClassOut {
  members: MemberOut[];
}

export type StudentGradeView = GradeSummary;

export interface FeedPage {
  items: Post[];
  /** Open tareas the viewer has not delivered. Identical on every page — it
   *  rides outside pagination — so read it from the first page only. */
  pinned: Post[];
  next_cursor: string | null;
  /** When this load's ranking was frozen. Every page of one load shares it;
   *  it is also the `since` for the new-posts check. */
  as_of: string;
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
  tareas: Rubro;
  examenes: Rubro;
  ledger: LedgerBreakdown;
  faltas: { count: number; points: number };
  events: GradeEvent[];
}

export interface FaltaRow {
  record_id: number;
  /** A calendar date, "YYYY-MM-DD" — no time, no zone. */
  date: string;
  justified: boolean;
}

export interface ProfileHeader {
  id: number;
  username: string;
  name: string;
  bio: string;
  avatar_url: string | null;
  role: "student" | "teacher";
  is_me: boolean;
  aura_received: number;
  has_own_avatar: boolean;
  /** Present only for the owner and a teacher who teaches them. */
  grades?: { class_id: number; class_name: string; summary: GradeSummary }[];
}

export type ProfilePost = Post & {
  parent?: { id: number; author_username: string | null; excerpt: string };
};

export interface ProfilePostsPage {
  items: ProfilePost[];
  next_cursor: string | null;
}
