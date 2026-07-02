variable "name_prefix"  { type = string }
variable "environment"  { type = string }
variable "force_destroy" {
  type    = bool
  default = false
  description = "Allow destroying non-empty buckets (set true only for dev)"
}
