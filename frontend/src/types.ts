export interface User {
  id: number; username: string; full_name: string; email?: string; bio: string; location: string; website: string
  avatar_url: string | null; cover_url: string | null; created_at: string; posts_count: number; followers_count: number
  following_count: number; is_following: boolean; is_staff: boolean; is_active?: boolean
}
export interface PostImage { id: number; url: string; alt_text: string; created_at: string }
export interface Post {
  id: number; author: User; content: string; is_public: boolean; images: PostImage[]; likes_count: number
  comments_count: number; liked_by_me: boolean; shares_count: number; hashtags: string[]; created_at: string; updated_at: string
}
export interface Comment { id: number; post: number; author: User; parent: number | null; content: string; created_at: string; updated_at: string }
export interface Notification { id: number; actor: User; kind: 'like'|'comment'|'follow'|'message'; post: number | null; post_preview: string; is_read: boolean; created_at: string }
export interface Message { id: number; conversation: number; sender: User; body: string; created_at: string; read_at: string | null }
export interface Conversation { id: number; participants: User[]; last_message: Message | null; unread_count: number; updated_at: string }
export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
