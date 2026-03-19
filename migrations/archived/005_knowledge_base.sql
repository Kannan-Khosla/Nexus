-- Migration: Add knowledge base support
-- Created: 2024
-- Dependencies: Requires migrations/001_add_users_and_auth.sql to be run first

-- Create article_categories table (hierarchical categories)
CREATE TABLE IF NOT EXISTS public.article_categories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  slug text NOT NULL UNIQUE, -- URL-friendly identifier
  parent_id uuid REFERENCES public.article_categories(id) ON DELETE CASCADE,
  description text,
  order_index integer NOT NULL DEFAULT 0,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Create article_tags table
CREATE TABLE IF NOT EXISTS public.article_tags (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  slug text NOT NULL UNIQUE,
  description text,
  color text, -- Hex color for UI display
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Create articles table
CREATE TABLE IF NOT EXISTS public.articles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  slug text NOT NULL UNIQUE,
  content text NOT NULL, -- Markdown or HTML content
  excerpt text, -- Short summary for listings
  category_id uuid REFERENCES public.article_categories(id) ON DELETE SET NULL,
  author_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
  views integer NOT NULL DEFAULT 0,
  helpful integer NOT NULL DEFAULT 0,
  not_helpful integer NOT NULL DEFAULT 0,
  is_featured boolean NOT NULL DEFAULT false,
  is_pinned boolean NOT NULL DEFAULT false,
  meta_keywords text[], -- Array of keywords for SEO
  meta_description text, -- Meta description for SEO
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz,
  last_viewed_at timestamptz
);

-- Create article_tag_mappings table (many-to-many relationship)
CREATE TABLE IF NOT EXISTS public.article_tag_mappings (
  article_id uuid NOT NULL REFERENCES public.articles(id) ON DELETE CASCADE,
  tag_id uuid NOT NULL REFERENCES public.article_tags(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (article_id, tag_id)
);

-- Create article_feedback table
CREATE TABLE IF NOT EXISTS public.article_feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  article_id uuid NOT NULL REFERENCES public.articles(id) ON DELETE CASCADE,
  user_id uuid REFERENCES public.users(id) ON DELETE SET NULL, -- Null for anonymous feedback
  helpful boolean NOT NULL, -- true = helpful, false = not helpful
  comment text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(article_id, user_id) -- One feedback per user per article
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_article_categories_parent_id ON public.article_categories(parent_id);
CREATE INDEX IF NOT EXISTS idx_article_categories_slug ON public.article_categories(slug);
CREATE INDEX IF NOT EXISTS idx_article_categories_is_active ON public.article_categories(is_active);
CREATE INDEX IF NOT EXISTS idx_article_categories_order_index ON public.article_categories(order_index);

CREATE INDEX IF NOT EXISTS idx_article_tags_slug ON public.article_tags(slug);
CREATE INDEX IF NOT EXISTS idx_article_tags_name ON public.article_tags(name);

CREATE INDEX IF NOT EXISTS idx_articles_category_id ON public.articles(category_id);
CREATE INDEX IF NOT EXISTS idx_articles_author_id ON public.articles(author_id);
CREATE INDEX IF NOT EXISTS idx_articles_status ON public.articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_slug ON public.articles(slug);
CREATE INDEX IF NOT EXISTS idx_articles_is_featured ON public.articles(is_featured);
CREATE INDEX IF NOT EXISTS idx_articles_is_pinned ON public.articles(is_pinned);
CREATE INDEX IF NOT EXISTS idx_articles_created_at ON public.articles(created_at);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON public.articles(published_at);
CREATE INDEX IF NOT EXISTS idx_articles_status_published_at ON public.articles(status, published_at);

-- Full-text search index for articles (PostgreSQL)
CREATE INDEX IF NOT EXISTS idx_articles_search ON public.articles USING gin(to_tsvector('english', title || ' ' || COALESCE(excerpt, '') || ' ' || content));

CREATE INDEX IF NOT EXISTS idx_article_tag_mappings_article_id ON public.article_tag_mappings(article_id);
CREATE INDEX IF NOT EXISTS idx_article_tag_mappings_tag_id ON public.article_tag_mappings(tag_id);

CREATE INDEX IF NOT EXISTS idx_article_feedback_article_id ON public.article_feedback(article_id);
CREATE INDEX IF NOT EXISTS idx_article_feedback_user_id ON public.article_feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_article_feedback_helpful ON public.article_feedback(helpful);
CREATE INDEX IF NOT EXISTS idx_article_feedback_created_at ON public.article_feedback(created_at);

-- Add comments for documentation
COMMENT ON TABLE public.article_categories IS 'Hierarchical categories for organizing knowledge base articles';
COMMENT ON TABLE public.article_tags IS 'Tags for categorizing and searching articles';
COMMENT ON TABLE public.articles IS 'Knowledge base articles with full-text search support';
COMMENT ON TABLE public.article_tag_mappings IS 'Many-to-many relationship between articles and tags';
COMMENT ON TABLE public.article_feedback IS 'User feedback on article helpfulness';

