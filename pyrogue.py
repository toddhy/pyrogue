#!/usr/bin/python3

import tcod as tcod

# size of window
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

# size of map
MAP_WIDTH = 80
MAP_HEIGHT = 45

LIMIT_FPS = 20 # 20 frames per second maximum

color_dark_wall = tcod.Color(0, 0, 100)
color_dark_ground = tcod.Color(50, 50, 150)

font_path = 'arial10x10.png'
font_flags = tcod.FONT_TYPE_GREYSCALE | tcod.FONT_LAYOUT_TCOD

window_title = 'pyrogue'
fullscreen = False

player_x = SCREEN_WIDTH // 2
player_y = SCREEN_HEIGHT // 2

class Tile:
	# a tile of the map and its properties
	def __init__(self, blocked, block_sight = None):
		self.blocked = blocked

		# by default, if a tile is blocked, it also blocks sight
		####### Try to understand this later ########
		if block_sight is None: block_sight = blocked
		self.block_sight = block_sight

class Object:
	# this is a generic object: the player, a monster, an item, the stairs, etc.
	# it's always represented by a character on the screen.
	def __init__(self, x, y, char, color):
		self.x = x
		self.y = y
		self.char = char
		self.color = color

	def move(self, dx, dy):
		# move by the given amount, if the destination is not blocked
		if not map[self.x + dx][self.y + dy].blocked:
			self.x += dx
			self.y += dy

	def draw(self):
		# set the color and then draw the character that represented this object at its position
		tcod.console_set_default_foreground(con, self.color)
		tcod.console_put_char(con, self.x, self.y, self.char, tcod.BKGND_NONE)

	def clear(self):
		# erase the character that represents this object
		tcod.console_put_char(con, self.x, self.y, ' ', tcod.BKGND_NONE)

def make_map():
	global map

	# fill map with "unblocked" tiles
	map = [
		[Tile(False) for y in range(MAP_HEIGHT)]
		for x in range (MAP_WIDTH)
	]

	map[30][22].blocked = True
	map[30][22].block_sight = True
	map[50][22].blocked = True
	map[50][22].block_sight = True

def render_all():
	global color_light_wall
	global color_light_ground

	# go through all the tiles, and set their background color
	for y in range(MAP_HEIGHT):
		for x in range(MAP_WIDTH):
			wall = map[x][y].block_sight
			if wall:
				tcod.console_set_char_background(con, x, y, color_dark_wall, tcod.BKGND_SET)
			else:
				tcod.console_set_char_background(con, x, y, color_dark_ground, tcod.BKGND_SET)

	# draw all objects in the list
	for object in objects:
		object.draw()

	# blit the contents of "con" to the root console and present it
	tcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)

def handle_keys():
	# key = tcod.console_check_for_keypress() # Real time
	key = tcod.console_wait_for_keypress(True)
	if key.vk == tcod.KEY_ENTER and key.lalt:
		#Alt+Enter fullscreen
		tcod.console_set_fullscreen(not tcod.console_is_fullscreen())
	elif key.vk == tcod.KEY_ESCAPE:
		return True #exit game
	global player_x, player_y

	# movement keys
	if tcod.console_is_key_pressed(tcod.KEY_UP):
		player.move(0, -1)
	elif tcod.console_is_key_pressed(tcod.KEY_DOWN):
		player.move(0, 1)
	elif tcod.console_is_key_pressed(tcod.KEY_LEFT):
		player.move(-1, 0)
	elif tcod.console_is_key_pressed(tcod.KEY_RIGHT):
		player.move(1, 0)

#########################################
# Initialization & Main Loop
#########################################

tcod.console_set_custom_font(font_path, font_flags)
tcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT,window_title, fullscreen)
tcod.sys_set_fps(LIMIT_FPS)
con = tcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)

# create object representing player
player = Object(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, '@', tcod.white)

# create an npc
npc = Object(SCREEN_WIDTH // 2 - 5, SCREEN_HEIGHT // 2, '@', tcod.yellow)

# the list of objects
objects = [npc, player]

#generate map (at this point it's not drawn to the screen)
make_map()

while not tcod.console_is_window_closed():

	# render the screen
	render_all()

	tcod.console_flush()

	#erase all objects at their old locations, before they move
	for object in objects:
		object.clear()

	# handle keys and exit game if needed
	exit = handle_keys()
	if exit:
		break
