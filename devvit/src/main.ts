import { Devvit } from '@devvit/public-api';

const WEBHOOK_URL = 'https://idella-ariose-lan.ngrok-free.dev/ingest';

Devvit.addTrigger({
  event: 'PostSubmit',
  async handler(event, context) {
    const post = event.post;
    if (!post) return;

    const payload = {
      id: post.id,
      title: post.title ?? '',
      body: post.selftext ?? '',
      author: post.authorName ?? '',
      subreddit: post.subredditName ?? '',
      url: post.permalink ? `https://www.reddit.com${post.permalink}` : '',
      upvotes: post.upvotes ?? 0,
      comments: post.numComments ?? 0,
      timestamp: new Date().toISOString(),
      signal_type: 'post',
    };

    await fetch(WEBHOOK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
});

Devvit.addTrigger({
  event: 'CommentSubmit',
  async handler(event, context) {
    const comment = event.comment;
    if (!comment) return;

    const payload = {
      id: comment.id,
      title: '',
      body: comment.body ?? '',
      author: comment.authorName ?? '',
      subreddit: comment.subredditName ?? '',
      url: comment.permalink ? `https://www.reddit.com${comment.permalink}` : '',
      upvotes: comment.upvotes ?? 0,
      comments: 0,
      timestamp: new Date().toISOString(),
      signal_type: 'comment',
    };

    await fetch(WEBHOOK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
});

Devvit.configure({
  redditAPI: true,
});

export default Devvit;
