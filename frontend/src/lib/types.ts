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
