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
export interface Notification { id: number; actor: User; kind: 'like'|'comment'|'follow'|'message'|'call'|'missed_call'|'declined_call'|'mention'|'story_reply'|'story_reaction'; post: number | null; comment: number | null; story: number | null; story_author_id: number | null; post_preview: string; is_read: boolean; created_at: string }
export interface Story { id: number; author: User; media_url: string; media_type: 'image'|'video'; caption: string; reactions_count: number; reacted_by_me: boolean; created_at: string; expires_at: string }
export interface StoryReply { id: number; author: User; content: string; created_at: string }
export interface Reel { id: number; author: User; video_url: string; thumbnail_url: string | null; caption: string; filter_name: 'none'|'vivid'|'mono'|'warm'|'vintage'; shares_count: number; likes_count: number; comments_count: number; liked_by_me: boolean; saved_by_me: boolean; created_at: string }
export interface ReelComment { id: number; author: User; content: string; created_at: string }
export interface Call { id: number; conversation: number; caller: User; recipient: User; kind: 'audio'|'video'; status: 'ringing'|'accepted'|'rejected'|'ended'|'missed'; offer: string; answer: string; created_at: string; answered_at: string | null; ended_at: string | null }
export interface Message { id: number; conversation: number; sender: User; body: string; kind: 'text'|'call'; call_type: 'audio'|'video'|''; call_status: string; created_at: string; read_at: string | null }
export interface Conversation { id: number; participants: User[]; last_message: Message | null; unread_count: number; updated_at: string }
export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
