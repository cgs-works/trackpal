# Use a Dedicated Table for Client Messaging Blocks

Client Messaging Blocks are stored in a dedicated tenant-scoped table instead of on `Client` because the block applies only to WhatsApp identities that are not registered as clients. This preserves the existing Client activation/deactivation model for registered clients while allowing admins to list and unblock non-client identities without creating placeholder Client records.
